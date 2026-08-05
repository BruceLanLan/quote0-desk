"""Hermes 任务台卡：本机 hermes-agent gateway 的定时任务概览，只读展示，
不在这张卡里触发/暂停/编辑任何任务——贴一下 NFC 触发/批准是完全不同量级的
操作，需要单独设计安全边界，不顺手放进这张展示卡里。

gateway 没在跑或没配 HERMES_API_KEY 时优雅显示"未接入"，不报错——这是
用户本机的可选基础设施，公开仓库的绝大多数使用者不会有这个东西，见
providers/hermes.py 的降级契约。

任务的 name/schedule 字段用 .get() 防御式取，拿不到就不显示那部分细节，
不假设一个没有把握的 JSON 形状。
"""
from __future__ import annotations

from canvas.template import simple_data
from providers.hermes import fetch as fetch_hermes


def _job_line(job: dict) -> str:
    """schedule 字段真机验证前假设是字符串，真实 gateway 返回的其实是
    `{"kind": "cron", "expr": "...", "display": "..."}` 这样的字典——顶层
    job 对象另有一份摊平好的 `schedule_display`，优先用这个；两者都没有
    再退到 schedule 字典内部的 display 键，最后才原样兜底，不假设固定形状。
    """
    name = job.get("name") or job.get("id", "未命名任务")
    schedule = job.get("schedule_display")
    if not schedule:
        raw = job.get("schedule")
        schedule = raw.get("display") if isinstance(raw, dict) else raw
    return f"· {name}（{schedule}）" if schedule else f"· {name}"


def build() -> dict:
    hermes = fetch_hermes()

    if not hermes.get("available"):
        reason_label = {
            "gateway_not_running": "gateway 未启动",
            "no_key": "未配置 HERMES_API_KEY",
            "http_error": "gateway 响应异常",
            "bad_response": "gateway 返回格式异常",
        }.get(hermes.get("reason"), "未接入")
        title = "Hermes 任务台"
        message = f"未接入 hermes-agent（{reason_label}）"
        footer = "quote0-desk · Hermes Agent"
        data = simple_data(title=title, message=message, footer=footer)
        return {"data": data, "alias": "Hermes 任务台", "link": ""}

    jobs = hermes["jobs"]
    title = f"Hermes 任务台 · {hermes['job_count']} 个任务"
    if not jobs:
        message = "暂无定时任务"
    else:
        message = "\n".join(_job_line(j) for j in jobs[:4])
        if len(jobs) > 4:
            message += f"\n…还有 {len(jobs) - 4} 个"
    footer = "quote0-desk · Hermes Agent"

    data = simple_data(title=title, message=message, footer=footer)
    return {"data": data, "alias": "Hermes 任务台", "link": ""}
