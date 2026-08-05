"""Hermes 收件箱：只存"最近一条 Hermes agent 推来的消息"，给 cards/hermes_inbox.py 读。

跟 providers/hermes.py（只读展示 gateway 的定时任务列表，我们主动去问 gateway）
是完全反方向的两条线——这条是 gateway 主动推给我们（经 hermes-quote0 插件的
send() 调 server.py 的 /api/hermes_inbox），我们只是被动接收、存最新一条、
覆盖式，不建消息队列/历史，这张卡就是显示"最新一条"，不是收件箱 App。
"""
from __future__ import annotations

import json
import os
import time

STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "hermes_inbox_state.json")

MAX_MESSAGE_LENGTH = 500  # 防止一条离谱长的消息把 Text API 的展示区撑爆


def receive(message: str) -> dict:
    """存一条新消息（覆盖旧的），返回存下的状态。"""
    text = str(message or "").strip()[:MAX_MESSAGE_LENGTH]
    state = {"message": text, "received_at": time.time()}
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return state


def latest() -> dict | None:
    if not os.path.exists(STATE_PATH):
        return None
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
