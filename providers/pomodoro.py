"""番茄钟：贴一下 NFC 开始一个专注块，到点自动推一张"结束了"的通知——
不依赖"自动轮换"这个布防开关（默认关闭），因为贴 NFC 开始本身就是用户
明确的意图，见 `scheduler.request_push_urgent()` 的文档。

墨水屏刷新慢、不能走秒——显示起止时刻（"16:20 → 16:45"）是设备约束下
的正确设计，不是妥协：贴一下看一眼就知道还剩多久、什么时候该期待被
打断，跟手机上转动的圈是两种不同的心智模型，各有适用场景。

专注块进行中时会调 `scheduler.pause_rotation()`，避免"专注中"这张卡被
下一次常规轮换覆盖掉；到点或提前结束都会 `resume_rotation()`。
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime

import config
import scheduler

STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pomodoro_state.json")

FINISHED_GLOW_SECONDS = 300  # 到点之后，"这一轮结束了"这句话在卡面上停留多久


def _load() -> dict:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save(state: dict):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _fmt(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M")


def status() -> dict:
    """当前番茄钟状态，纯查询、不推进任何状态——跟 `check_due()` 的
    区别是它会真的清空到期的 session，这个只读。"""
    state = _load()
    now = time.time()
    end_at = state.get("end_at")
    if end_at and now < end_at:
        return {"phase": "running", "start_label": _fmt(state["start_at"]), "end_label": _fmt(end_at)}
    finished_at = state.get("finished_at")
    if finished_at and now - finished_at < FINISHED_GLOW_SECONDS:
        return {"phase": "finished", "end_label": _fmt(finished_at)}
    return {"phase": "idle"}


def toggle() -> dict:
    """NFC 贴一下：空闲就开始一个专注块，进行中就提前结束。"""
    state = _load()
    now = time.time()
    end_at = state.get("end_at")
    if end_at and now < end_at:
        _save({"finished_at": now})
        scheduler.resume_rotation()
        return {"phase": "ended_early"}
    minutes = int(config.load().get("pomodoro_minutes", 25) or 25)
    start_at = now
    end_at = now + minutes * 60
    _save({"start_at": start_at, "end_at": end_at})
    scheduler.pause_rotation()
    return {"phase": "started", "start_label": _fmt(start_at), "end_label": _fmt(end_at)}


def check_due() -> bool:
    """由 scheduler 的 watcher 机制定期调用（不受布防约束）。一个专注块
    刚到点就清空 running 状态、恢复常规轮换、记录 `finished_at` 供卡面
    显示"这一轮结束了"，返回 True 让调用方触发一次插队推送。已经处理过
    的到期不会重复触发——清空后 `end_at` 不再满足"未到期"条件。"""
    state = _load()
    end_at = state.get("end_at")
    if not end_at or time.time() < end_at:
        return False
    _save({"finished_at": time.time()})
    scheduler.resume_rotation()
    return True


def _watch():
    if check_due():
        scheduler.request_push_urgent("pomodoro")


scheduler.register_watcher(_watch)
