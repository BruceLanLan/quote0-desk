"""M6 调度器：按周期轮换推送 `auto_push_cards` 里的卡。

移植自 pocket-prophet-dashboard/scheduler.py 的"后台 daemon 线程 + sleep
轮询"结构，但比那边简单——那边需要 `page_renderers` 字典是因为当时推送
路径按卡各写一份；这边 `push.push_card(name)` 已经把 Canvas/Image 两条
路径统一了，调度器不需要关心某张卡到底走哪个槽，只管"轮到谁就推谁"。

默认关闭（`auto_push_enabled=False`），要用户在 config 里显式打开——原因
同 pocket-prophet：设备被推起来的那一刻可能是用户自己想在 App 里操作，
自动推送会把那次手动操作覆盖掉，不能默认布防。
"""
import logging
import threading
from datetime import datetime, timedelta

import config
from push import push_card

log = logging.getLogger("quote0-desk.scheduler")

_thread = None
_stop_event = threading.Event()
_state_lock = threading.Lock()
_state = {
    "armed": False,
    "last_push_at": None,
    "last_push_card": None,
    "last_push_ok": None,
    "last_push_hint": None,
    "next_push_at": None,
}

DISARMED_POLL_SECONDS = 5  # 未布防时多久检查一次"是否被布防了"，让开关能及时生效
MIN_INTERVAL_MINUTES = 5


def get_state() -> dict:
    with _state_lock:
        return dict(_state)


def _next_card(cards: list, last: str) -> str:
    if last in cards:
        i = (cards.index(last) + 1) % len(cards)
    else:
        i = 0
    return cards[i]


def _tick():
    cfg = config.load()
    cards = cfg.get("auto_push_cards") or []
    if not cards:
        log.info("自动推送已布防但 auto_push_cards 为空，本轮跳过")
        return

    card = _next_card(cards, cfg.get("_auto_push_last_card"))

    try:
        result = push_card(card)
    except Exception as e:
        result = {"ok": False, "reason": "error", "hint": str(e)}
        log.warning("自动推送 %s 失败: %s", card, e)
    else:
        log.info("自动推送 %s: %s", card, result)

    config.update(_auto_push_last_card=card)
    with _state_lock:
        _state["last_push_at"] = datetime.now().isoformat()
        _state["last_push_card"] = card
        _state["last_push_ok"] = result.get("ok")
        _state["last_push_hint"] = result.get("hint")


def _loop():
    while not _stop_event.is_set():
        cfg = config.load()
        armed = bool(cfg.get("auto_push_enabled"))
        interval_min = max(MIN_INTERVAL_MINUTES, int(cfg.get("auto_push_interval_minutes", 10) or 10))

        with _state_lock:
            _state["armed"] = armed

        if not armed:
            with _state_lock:
                _state["next_push_at"] = None
            _stop_event.wait(DISARMED_POLL_SECONDS)
            continue

        _tick()
        with _state_lock:
            _state["next_push_at"] = (datetime.now() + timedelta(minutes=interval_min)).isoformat()
        _stop_event.wait(interval_min * 60)


def start():
    """启动后台线程。重复调用是安全的（线程已在跑就不重复起）。"""
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()
    log.info("自动推送调度线程已启动（默认未布防，需在 config 里 auto_push_enabled=true）")
