"""Claude Code 状态灯卡：活跃指示 + 项目名 + 今日 token/成本估算。"""
from canvas.template import simple_card, simple_data
from providers.claude_activity import scan


def build() -> dict:
    s = scan()
    indicator = "● 活跃中" if s["active"] else "○ 空闲"
    title = f"{indicator}"
    project_line = f"项目：{s['project']}" if s["project"] else "最近无活动"
    usage_line = f"今日 {s['today_tokens']:,} tokens · 约 ${s['estimated_cost_usd']:.2f}"
    message = f"{project_line}\n{usage_line}"
    footer = "quote0-desk · Claude Code 状态灯"

    data = simple_data(title=title, message=message, footer=footer)
    window_data = simple_card(title=title, message=message, footer=footer,
                               title_size=20, message_size=14, footer_size=11)
    return {"data": data, "window_data": window_data, "alias": "状态灯", "link": ""}
