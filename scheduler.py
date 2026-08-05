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

# 事件驱动的一次性插队推送——Hermes 消息刚到这类"有时效性"的内容不应该
# 被 round-robin 埋掉（12+ 张卡、10 分钟一轮，最坏要等 2 小时）。只是个
# 待处理名单，不是队列本身的调度权威——_loop() 才是唯一决定"到底推不推"
# 的地方，见下方 request_push() 的文档。
_pending_lock = threading.Lock()
_pending_cards: list[str] = []

# 跟上面那条的区别：urgent 不受布防开关约束。番茄钟到点提醒是"用户已经
# 用一次物理动作（贴 NFC 开始专注）明确表达了意图，现在只是在等一个必然
# 会发生的到期通知"——不应该因为"没开自动轮换"这个不相关的开关被吞掉。
# 绝大多数场景应该用 request_push()，这个只服务这一类狭窄场景，见
# request_push_urgent() 的文档。
_pending_urgent: list[str] = []

# 暂停常规轮换但不影响插队推送——番茄钟专注块进行中时用，避免"专注中"
# 这张卡被下一次轮换覆盖掉。调用方（providers/pomodoro.py）负责在专注块
# 结束时调用 resume_rotation()，scheduler 自己不知道"什么时候该恢复"。
_rotation_paused = threading.Event()

# 每次调度线程醒来（不论布防与否）都会被调用一次的回调列表——给"番茄钟
# 到期检测"这类需要脱离布防开关、独立定期检查的逻辑用。scheduler 不关心
# 回调内部在检查什么业务状态，只负责按时调用它们，保持 scheduler.py 通用、
# 不耦合具体某张卡的逻辑。
_watchers: list = []

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


def request_push_urgent(card: str):
    """跟 request_push() 唯一的区别：**不受布防开关约束**，即使未布防
    （`auto_push_enabled=False`，这是默认状态）也会被推送。只给"用户已经
    通过一次明确的物理动作表达了意图，现在只是在等一个必然会发生的到期
    通知"这种狭窄场景用——目前唯一的例子是番茄钟到点：贴 NFC 开始专注块
    本身就是显式意图，25 分钟后的提醒不应该因为用户没开自动轮换（大多数
    人不会开）就完全收不到。**不要把这个当成常规推送的默认选项**，绝大
    多数事件驱动场景应该用 request_push()。
    """
    with _pending_lock:
        if card not in _pending_urgent:
            _pending_urgent.append(card)


def register_watcher(fn):
    """注册一个每次调度线程醒来都会被调用一次的回调（不论布防与否）。
    回调自己决定要不要调用 request_push_urgent()，scheduler 只负责按时
    调用它、吞掉它可能抛的异常（一个 watcher 报错不该拖垮整个调度线程）。
    """
    _watchers.append(fn)


def pause_rotation():
    """暂停常规轮换（不影响 request_push()/request_push_urgent() 的插队
    推送）——番茄钟专注块进行中时用。调用方负责在合适的时机调用
    resume_rotation()，scheduler 不会自己猜"该恢复了"。"""
    _rotation_paused.set()


def resume_rotation():
    _rotation_paused.clear()


def _run_watchers():
    for fn in _watchers:
        try:
            fn()
        except Exception as e:
            log.warning("watcher 报错（不影响其它 watcher 和常规调度）: %s", e)


def _pop_pending() -> str | None:
    with _pending_lock:
        return _pending_cards.pop(0) if _pending_cards else None


def _pop_urgent() -> str | None:
    with _pending_lock:
        return _pending_urgent.pop(0) if _pending_urgent else None


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


def _drain_urgent():
    """把 urgent 队列清空——不论布防与否都要在每次醒来时做这件事。跟
    watcher 一起放在 _loop() 顶部和 _sleep_until_next_tick() 的轮询里，
    是这个模块里两处"不受布防约束"的检查点，缺一个都会让番茄钟到点提醒
    在未布防（默认状态）时延迟到最长 DISARMED_POLL_SECONDS 或 interval_min
    才被发现。"""
    urgent = _pop_urgent()
    if urgent is not None:
        _tick_specific(urgent)


def _loop():
    while not _stop_event.is_set():
        _run_watchers()  # 番茄钟到期检测这类，不受布防开关约束
        _drain_urgent()

        cfg = config.load()
        armed = bool(cfg.get("auto_push_enabled"))
        interval_min = max(MIN_INTERVAL_MINUTES, int(cfg.get("auto_push_interval_minutes", 10) or 10))

        with _state_lock:
            _state["armed"] = armed

        if not armed:
            # 布防语义必须唯一：没布防就不该有任何常规自动推送，包括事件
            # 驱动的插队请求——不能让 request_push() 变成绕过这个开关的
            # 后门。urgent 队列不受这条约束，已经在上面 _drain_urgent()
            # 处理过了，这里清空的只是普通 pending。
            _clear_pending()
            with _state_lock:
                _state["next_push_at"] = None
            _stop_event.wait(DISARMED_POLL_SECONDS)
            continue

        if _rotation_paused.is_set():
            # 番茄钟专注块进行中：跳过本轮常规轮换，让"专注中"这张卡
            # 留在屏幕上，但插队/urgent 推送（已经在上面处理过）和布防
            # 开关的响应速度都不受影响。
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
    3. watcher 回调 + urgent 队列——不受布防约束，跟 _loop() 顶部同一套
       检查，这里也要做一遍，因为大部分时间调度线程都阻塞在这个函数里
       （常规轮换间隔可以长达数十分钟），不这样做的话番茄钟到点通知得
       等到当前这轮常规轮换周期结束才会被发现。
    """
    deadline = time.monotonic() + interval_min * 60
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if _stop_event.wait(min(DISARMED_POLL_SECONDS, remaining)):
            return  # 线程被要求整体停止
        _run_watchers()
        _drain_urgent()
        if not config.load().get("auto_push_enabled"):
            return  # 布防被中途关掉，提前结束这次等待，让下一轮循环立刻反映新状态
        if _rotation_paused.is_set():
            return  # 专注块中途开始了，提前结束这次等待，让 _loop() 顶部去跳过常规轮换
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
