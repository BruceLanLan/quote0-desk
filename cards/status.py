"""Claude Code 状态灯卡：活跃指示 + 项目名 + 配额/今日用量。

配额行优先读 providers/claude_quota.py（真实账号 5h/7d 配额百分比，回答
"离限额还有多远"）；拿不到（token 过期/端点不可用）就退回 JSONL 估算的
"今日 tokens/成本"（回答"用了多少"）——两个 provider 各自独立、互不依赖，
配额端点是未文档化的接口，说不准哪天就变形或消失，不能让它拖垮整张卡。
"""
from __future__ import annotations

from canvas.template import simple_card, simple_data
from providers.claude_activity import scan
from providers.claude_quota import fetch as fetch_quota


def _quota_line(quota: dict) -> str | None:
    if not quota.get("available"):
        return None
    parts = []
    five_hour = quota.get("five_hour")
    seven_day = quota.get("seven_day")
    if five_hour:
        parts.append(f"5h {five_hour['utilization']:.0f}%")
    if seven_day:
        parts.append(f"7d {seven_day['utilization']:.0f}%")
    return "配额 " + " · ".join(parts) if parts else None


def build() -> dict:
    s = scan()
    indicator = "● 活跃中" if s["active"] else "○ 空闲"
    title = f"{indicator}"
    project_line = f"项目：{s['project']}" if s["project"] else "最近无活动"
    usage_line = (_quota_line(fetch_quota())
                  or f"今日 {s['today_tokens']:,} tokens · 约 ${s['estimated_cost_usd']:.2f}")
    message = f"{project_line}\n{usage_line}"
    footer = "quote0-desk · Claude Code 状态灯"

    data = simple_data(title=title, message=message, footer=footer)
    window_data = simple_card(title=title, message=message, footer=footer,
                               title_size=20, message_size=14, footer_size=11)
    return {"data": data, "window_data": window_data, "alias": "状态灯", "link": ""}
