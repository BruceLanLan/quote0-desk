"""番茄钟卡：贴一下开始/结束专注块，屏幕显示起止时刻——墨水屏刷新慢、
不能走秒，"16:20 → 16:45"比试图模拟倒计时更符合这块屏幕的物理特性，
见 providers/pomodoro.py 顶部的说明。
"""
from __future__ import annotations

from canvas.template import simple_data
from config import nfc_base_url
from providers import pomodoro


def build() -> dict:
    s = pomodoro.status()
    if s["phase"] == "running":
        title = "专注中"
        message = f"{s['start_label']} → {s['end_label']}"
    elif s["phase"] == "finished":
        title = "这一轮结束了"
        message = f"{s['end_label']} 到点\n贴一下开始下一轮"
    else:
        title = "番茄钟"
        message = "贴一下开始专注"

    base = nfc_base_url()
    link = f"{base}/t/pomodoro" if base else ""
    data = simple_data(title=title, message=message, footer="quote0-desk · 番茄钟")
    return {"data": data, "alias": "番茄钟", "link": link}
