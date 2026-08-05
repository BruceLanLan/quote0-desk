"""Hermes 收件箱卡：展示 Hermes agent 经 hermes-quote0 插件推来的最新一条消息。

跟 cards/hermes.py（只读展示 gateway 的定时任务列表）是姊妹卡但方向相反：
那张是我们主动去问 gateway"有哪些定时任务"；这张是被动接收 gateway 主动
推来的内容（cron `deliver=quote0` 落地后，这张卡就是"第五个投递渠道"的
屏幕出口，见私有整合计划第 4 步）。

D2 安全设计决策：footer 固定写死"Hermes Agent"，不受 message 内容影响——
不管 agent 生成的文字里想不想署名，屏幕上永远能分辨这条内容的来源。
D1：这张卡不接受任何外部指定的 link，本轮不设 NFC 交互（是否要加回执动作
留到整合计划第 6 步「NFC 触发 cron job」时再决定，不在这一步顺手加）。
"""
from __future__ import annotations

from canvas.template import simple_data
from providers import hermes_inbox


def build() -> dict:
    state = hermes_inbox.latest()
    message = state["message"] if state and state.get("message") else "还没收到 Hermes agent 的消息"
    data = simple_data(title="Hermes 消息", message=message, footer="Hermes Agent")
    return {"data": data, "alias": "hermes_inbox", "link": ""}
