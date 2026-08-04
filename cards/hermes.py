"""Hermes 任务台卡：本机 hermes-agent gateway 的定时任务概览，只读展示，
不在这张卡里触发/暂停/编辑任何任务——那是 NFC 双向控制的范围（见
docs/PLAN-hermes-integration.md 第 6 步，需另行确认才做）。

gateway 没在跑或没配 HERMES_API_KEY 时优雅显示"未接入"，不报错——这是
用户本机的可选基础设施，公开仓库的绝大多数使用者不会有这个东西，见
providers/hermes.py 的降级契约。

真机验证过的字段只有任务的 id/name（见 docs/PLAN-hermes-integration.md
真机执行记录），其余字段（next_run_at、enabled 之类）用 .get() 防御式取，
拿不到就不显示那部分细节，不假设一个没验证过的 JSON 形状。
"""
from __future__ import annotations

from canvas.template import simple_data
from providers.hermes import fetch as fetch_hermes


def _job_line(job: dict) -> str:
    name = job.get("name") or job.get("id", "未命名任务")
    schedule = job.get("schedule") or job.get("cron")
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
