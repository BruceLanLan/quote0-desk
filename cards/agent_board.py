"""状态板卡：靠对话写入的多行记录，不是 provider 抓出来的仪表盘（见
`providers/agent_board.py` 的 D5 说明）。渲染走 `render/rows.py` 的
Image API 路径——多行表格 Text API 没有验证过能不能撑住，Image API 有
已验证的本地 PIL 渲染路径。
"""
from __future__ import annotations

from datetime import datetime

from providers import agent_board
from render.rows import build_rows_png


def build() -> dict:
    state = agent_board.board()
    rows = state.get("rows", []) if state else []

    if not rows:
        display_rows = [("状态板", "还没有记录，跟 Claude 说一句话试试")]
    else:
        display_rows = [
            (r["label"], f"{datetime.fromtimestamp(r['ts']).strftime('%H:%M')} · {r['value']}")
            for r in rows
        ]

    png = build_rows_png("状态板", display_rows, footer="quote0-desk · 状态板")
    return {"png": png, "alias": "状态板", "link": ""}
