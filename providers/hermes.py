"""Hermes Agent gateway 本地状态：只读接入用户本机可能在跑的 hermes-agent
gateway（NousResearch Hermes Agent 的自托管运行时，跟这个项目本身无关的
另一个本机基础设施——是否安装、是否常驻都不是 quote0-desk 的假设，公开仓库
的绝大多数使用者不会有这个东西）。

跟 providers/buddy.py 同一套纪律：只读、可选、永不抛异常、`available` 契约。

协议依据 docs/PLAN-hermes-integration.md 的真机验证记录（2026-08-04）：
- `GET /health` 不需要鉴权，只返回健康检查（platform/version）——先探这个，
  gateway 真的没在跑时不会因为缺 key 而误报"没配 key"，两种"不可用"原因
  分得清楚。
- `GET /api/jobs` 需要 Bearer token 鉴权（网关的 API_SERVER_KEY，回环地址
  也不放过），默认不含 paused/disabled 的任务，要看全量得加
  `?include_disabled=true`。

`API_SERVER_KEY` 只认环境变量 `HERMES_API_KEY`——真机验证时这把 key 是
内联传给 `hermes gateway run` 的，没有确认过的落盘位置；跟这个项目自己
`DOT_API_KEY` 的纪律一致：不猜文件路径，只读环境变量。
"""
from __future__ import annotations

import os

import requests

HEALTH_URL = "http://127.0.0.1:8642/health"
JOBS_URL = "http://127.0.0.1:8642/api/jobs"
TIMEOUT = 3  # 本地守护进程，超时给短一点，别让卡片推送等太久


def _api_key() -> str | None:
    return os.environ.get("HERMES_API_KEY") or None


def fetch() -> dict:
    """返回：
    `{"available": True, "jobs": [...], "job_count": int}`
    或
    `{"available": False, "reason": "gateway_not_running"|"no_key"|
      "http_error"|"bad_response"}`。

    永不抛异常——gateway 没开是正常状态，不是错误状态。
    """
    try:
        health = requests.get(HEALTH_URL, timeout=TIMEOUT)
    except requests.RequestException:
        return {"available": False, "reason": "gateway_not_running"}
    if not health.ok:
        return {"available": False, "reason": "http_error"}

    key = _api_key()
    if not key:
        return {"available": False, "reason": "no_key"}

    try:
        resp = requests.get(JOBS_URL, params={"include_disabled": "true"},
                             headers={"Authorization": f"Bearer {key}"}, timeout=TIMEOUT)
    except requests.RequestException:
        return {"available": False, "reason": "gateway_not_running"}
    if not resp.ok:
        return {"available": False, "reason": "http_error"}

    try:
        data = resp.json()
    except ValueError:
        return {"available": False, "reason": "bad_response"}

    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    return {
        "available": True,
        "jobs": jobs,
        "job_count": len(jobs),
    }
