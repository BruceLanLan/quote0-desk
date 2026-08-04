"""Claude Code 状态灯卡：活跃指示 + 项目名 + 配额/今日用量。

**活跃指示跟宠物卡用同一套语义、同一份判定代码**（2026-08-04 整合）。以前
这里自己实现了一遍 `running>0 or waiting>0`、只输出"● 活跃中 / ○ 空闲"这个
自造的二元状态，而宠物卡用的是官方 claude-desktop-buddy 的六态语义
（sleep/idle/busy/attention/…），同一个 buddy-bridge 快照被两处各解读一遍，
措辞还对不上——"在等你批准"在状态灯上只会显示成一个笼统的"活跃中"。现在两边
都调 `providers/buddy.py` 的 `base_state()`，标签也统一用官方状态名的中文说法。

信号优先级不变：优先读 providers/buddy.py（本机 buddy-bridge 守护进程如果
在跑，是 hook 实时上报的 running/waiting，比"转录文件 mtime 是否在窗口内"
这种事后猜测准得多）；没有这个守护进程（公开仓库的大多数使用者都没有，这是
用户自己的另一个本机项目，不是这个仓库的依赖）就退回
providers/claude_activity.py 的 mtime 判断——那边只能区分"最近写过没有"，
所以降级后只在 busy / idle 之间二选一，不会假装能分辨"是不是在等审批"
（宠物卡降级时也是同一个取舍，那边多一个 sleep，因为它有 git commit 时间
这个更长尺度的信号，转录文件 mtime 没有对应物）。项目名固定读
claude_activity——buddy-bridge 的 snapshot 没有单独暴露 cwd，没必要为了这
一个字段去解析更深层的 sessions[] 结构。

配额行优先读 providers/claude_quota.py（真实账号 5h/7d 配额百分比，回答
"离限额还有多远"）；拿不到（token 过期/端点不可用）就退回 JSONL 估算的
"今日 tokens/成本"（回答"用了多少"）——两个 provider 各自独立、互不依赖，
配额端点是未文档化的接口，说不准哪天就变形或消失，不能让它拖垮整张卡。
这条降级链跟上面那条完全正交：配额端点挂了不影响活跃判定，buddy-bridge
没开也不影响配额行。
"""
from __future__ import annotations

from canvas.template import simple_data
from providers import buddy as buddy_provider
from providers.claude_activity import scan
from providers.claude_quota import fetch as fetch_quota

# 官方状态名 → 卡面措辞。跟 render/pet.py 的 STATE_LABEL 是同一套语义，
# 只是状态灯是一行标题、不画图，说法更短。
STATE_INDICATOR = {
    "attention": "◉ 等你批准",
    "busy": "● 工作中",
    "idle": "○ 空闲",
}


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


def state_name(activity: dict, buddy: dict) -> str:
    """当前该显示哪个官方状态名。buddy-bridge 在线就用它的判定（跟宠物卡
    同一份代码）；不在线退回转录文件 mtime，只能给出 busy / idle。"""
    state = buddy_provider.base_state(buddy)
    if state is not None:
        return state
    return "busy" if activity["active"] else "idle"


def build() -> dict:
    s = scan()
    buddy = buddy_provider.fetch()
    title = STATE_INDICATOR.get(state_name(s, buddy), "○ 空闲")
    project_line = f"项目：{s['project']}" if s["project"] else "最近无活动"
    usage_line = (_quota_line(fetch_quota())
                  or f"今日 {s['today_tokens']:,} tokens · 约 ${s['estimated_cost_usd']:.2f}")
    message = f"{project_line}\n{usage_line}"
    footer = "quote0-desk · Claude Code 状态灯"

    data = simple_data(title=title, message=message, footer=footer)
    return {"data": data, "alias": "状态灯", "link": ""}
