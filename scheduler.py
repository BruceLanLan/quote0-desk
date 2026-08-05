"""M6 调度器：按周期轮换推送 `auto_push_cards` 里的卡。

移植自 pocket-prophet-dashboard/scheduler.py 的"后台 daemon 线程 + sleep
轮询"结构，但比那边简单——那边需要 `page_renderers` 字典是因为当时推送
路径按卡各写一份；这边 `push.push_card(name)` 已经把 Canvas/Image 两条
路径统一了，调度器不需要关心某张卡到底走哪个槽，只管"轮到谁就推谁"。

默认关闭（`auto_push_enabled=False`），要用户在 config 里显式打开——原因
同 pocket-prophet：设备被推起来的那一刻可能是用户自己想在 App 里操作，
自动推送会把那次手动操作覆盖掉，不能默认布防。
"""
from __future__ import annotations

import logging
import threading
import time
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

# 事件驱动的一次性插队推送——Hermes 消息刚到、番茄钟到点这类"有时效性"的
# 内容不应该被 round-robin 埋掉（12+ 张卡、10 分钟一轮，最坏要等 2 小时）。
# 只是个待处理名单，不是队列本身的调度权威——_loop() 才是唯一决定"到底
# 推不推"的地方，见下方 request_push() 的文档。
_pending_lock = threading.Lock()
_pending_cards: list[str] = []

DISARMED_POLL_SECONDS = 5  # 未布防时多久检查一次"是否被布防了"，让开关能及时生效
MIN_INTERVAL_MINUTES = 5


def get_state() -> dict:
    with _state_lock:
        return dict(_state)


def request_push(card: str):
    """请求尽快插队推一次某张卡，跳过常规轮换的等待——不直接调用
    push_card()，而是登记进这个待处理名单，由 _loop() 在下次醒来
    （≤ DISARMED_POLL_SECONDS）时消费。这样事件触发的推送和常规轮换
    共用同一个调度线程，不会有两个线程同时调 Dot API 的竞态。

    **布防语义必须唯一**：这里只是登记"有一个待处理请求"，真正会不会推
    完全由 _loop() 决定——未布防时 _loop() 会直接丢弃所有待处理请求，
    不会因为调用了这个函数就绕过布防开关，见 _loop() 里 `_clear_pending()`
    那一行。调用方（`/api/hermes_inbox`、番茄钟到点这类事件）不需要
    自己判断当前布防状态，丢给这里就行。
    """
    with _pending_lock:
        if card not in _pending_cards:
            _pending_cards.append(card)


def _pop_pending() -> str | None:
    with _pending_lock:
        return _pending_cards.pop(0) if _pending_cards else None


def _clear_pending():
    with _pending_lock:
        _pending_cards.clear()


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


def _tick_specific(card: str):
    """事件驱动的插队推送：推一张指定的卡，**不**走 `_next_card()` 轮换、
    **不**更新 `_auto_push_last_card`——这次推送是插队，不能打乱常规轮换的
    游标，否则下一次常规轮换该轮到谁就变得不可预测了。跟 `_tick()` 唯一
    的区别就是"卡是外部指定的还是自己算的"，其余（错误处理、状态记录）
    完全一致。"""
    try:
        result = push_card(card)
    except Exception as e:
        result = {"ok": False, "reason": "error", "hint": str(e)}
        log.warning("事件驱动推送 %s 失败: %s", card, e)
    else:
        log.info("事件驱动推送 %s: %s", card, result)

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
            # 布防语义必须唯一：没布防就不该有任何自动推送，包括事件驱动的
            # 插队请求——不能让 request_push() 变成绕过这个开关的后门。
            _clear_pending()
            with _state_lock:
                _state["next_push_at"] = None
            _stop_event.wait(DISARMED_POLL_SECONDS)
            continue

        _tick()
        with _state_lock:
            _state["next_push_at"] = (datetime.now() + timedelta(minutes=interval_min)).isoformat()
        _sleep_until_next_tick(interval_min)


def _sleep_until_next_tick(interval_min: int):
    """按 interval_min 分钟睡，但每 DISARMED_POLL_SECONDS 秒醒一次检查：

    1. 布防开关有没有被中途关掉——之前是一次性 sleep(interval_min*60)，
       用户在设置页关掉布防、看到"已保存"之后，实际最长要等 interval_min
       （默认至少 5 分钟）才会真正停止推送，这段时间仪表盘还在显示
       "已布防·下次约 HH:MM"，是个会误导人的假开关。
    2. 有没有事件驱动的插队请求（`request_push()` 登记的）——命中就立刻
       用 `_tick_specific()` 推掉，**不提前结束这次等待**、也不碰
       `next_push_at`：常规轮换的时间表和游标完全不受插队影响，插队
       推送只是塞进了这段等待期里的一次"额外"推送。
    """
    deadline = time.monotonic() + interval_min * 60
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if _stop_event.wait(min(DISARMED_POLL_SECONDS, remaining)):
            return  # 线程被要求整体停止
        if not config.load().get("auto_push_enabled"):
            return  # 布防被中途关掉，提前结束这次等待，让下一轮循环立刻反映新状态
        pending = _pop_pending()
        if pending is not None:
            _tick_specific(pending)


def start():
    """启动后台线程。重复调用是安全的（线程已在跑就不重复起）。"""
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()
    log.info("自动推送调度线程已启动（默认未布防，需在 config 里 auto_push_enabled=true）")
