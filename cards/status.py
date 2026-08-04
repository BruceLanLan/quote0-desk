"""Claude Code 状态灯卡：活跃指示 + 项目名 + 配额/今日用量。

活跃指示优先读 providers/buddy.py（本机 buddy-bridge 守护进程如果在跑，
是 hook 实时上报的 running/waiting，比"转录文件 mtime 是否在窗口内"这种
事后猜测准得多）；没有这个守护进程（公开仓库的大多数使用者都没有，这是
用户自己的另一个本机项目，不是这个仓库的依赖）就退回
providers/claude_activity.py 的 mtime 判断。项目名固定读 claude_activity——
buddy-bridge 的 snapshot 没有单独暴露 cwd，没必要为了这一个字段去解析
更深层的 sessions[] 结构。

配额行优先读 providers/claude_quota.py（真实账号 5h/7d 配额百分比，回答
"离限额还有多远"）；拿不到（token 过期/端点不可用）就退回 JSONL 估算的
"今日 tokens/成本"（回答"用了多少"）——两个 provider 各自独立、互不依赖，
配额端点是未文档化的接口，说不准哪天就变形或消失，不能让它拖垮整张卡。
"""
from __future__ import annotations

from canvas.template import simple_data
from providers.buddy import fetch as fetch_buddy
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


def _active(s: dict, buddy: dict) -> bool:
    if buddy.get("available"):
        return buddy.get("running", 0) > 0 or buddy.get("waiting", 0) > 0
    return s["active"]


def build() -> dict:
    s = scan()
    buddy = fetch_buddy()
    indicator = "● 活跃中" if _active(s, buddy) else "○ 空闲"
    title = f"{indicator}"
    project_line = f"项目：{s['project']}" if s["project"] else "最近无活动"
    usage_line = (_quota_line(fetch_quota())
                  or f"今日 {s['today_tokens']:,} tokens · 约 ${s['estimated_cost_usd']:.2f}")
    message = f"{project_line}\n{usage_line}"
    footer = "quote0-desk · Claude Code 状态灯"

    data = simple_data(title=title, message=message, footer=footer)
    return {"data": data, "alias": "状态灯", "link": ""}
