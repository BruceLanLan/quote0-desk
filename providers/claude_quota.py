"""Claude 账号配额（5 小时/7 天用量百分比），只读 `~/.claude/.credentials.json`。

参考社区项目 `zellux/quote0-token-usage-dash` 的做法：Claude Code 登录后会
把 OAuth token 存在这个文件里，`GET https://api.anthropic.com/api/oauth/usage`
能拿到真实的配额百分比——这比 `providers/claude_activity.py` 扫本地 JSONL
转录文件估算的"今日 token/成本"更有用：后者只回答"用了多少"，这个端点直接
回答"离配额上限还有多远"。

**只读，绝不刷新/绝不回写这个文件**——那个参考项目会在 401 时用 refresh
token 换新 access token 再写回文件，这个动作在这里不安全：这个凭据文件
同时被"当前正在跑的 Claude Code 会话"持有着内存里的一份，我们的进程去
改磁盘上那份，有把用户当前会话的登录状态弄坏的风险，不值得为了一张状态灯
卡冒这个险。token 过期就老实报"配额未知"，Claude Code 自己会在正常使用
里把它刷新回来，不需要我们插手。

这个端点没有公开文档，字段形状是抄参考项目代码里的解析逻辑（`utilization`/
`resets_at`，嵌在 `five_hour`/`seven_day` 键下），本机验证时 token 已过期
（`expiresAt` 早于当前时间），没能拿到一次成功响应核对真实形状——所以这里
按"缺字段就当不可用"处理，不假设端点一定长这样，形状不对就优雅降级，不是
让调用方再包一层 try/except。
"""
from __future__ import annotations

import json
import os
import time

import requests

CREDENTIALS_PATH = os.path.expanduser("~/.claude/.credentials.json")
USAGE_ENDPOINT = "https://api.anthropic.com/api/oauth/usage"
TIMEOUT = 10


def _load_access_token() -> str | None:
    if not os.path.exists(CREDENTIALS_PATH):
        return None
    try:
        with open(CREDENTIALS_PATH) as f:
            data = json.load(f)
        oauth = data["claudeAiOauth"]
    except (json.JSONDecodeError, OSError, KeyError):
        return None

    expires_at = oauth.get("expiresAt")
    if expires_at and time.time() * 1000 > float(expires_at):
        return None  # 已过期，不刷新，直接报不可用
    return oauth.get("accessToken")


def _window(raw: dict | None) -> dict | None:
    if not raw or "utilization" not in raw:
        return None
    return {"utilization": float(raw["utilization"]), "resets_at": raw.get("resets_at")}


def fetch() -> dict:
    """返回 `{"available": True, "five_hour": {...}, "seven_day": {...}}` 或
    `{"available": False, "reason": "no_credentials"|"expired"|"http_error"|"network_error"}`。
    永不抛异常——跟 dot.py 的 `_post_structured` 一个纪律：失败态是返回值，
    不是异常，调用方（cards/status.py）直接拿 `available` 判断降级。
    """
    token = _load_access_token()
    if not token:
        return {"available": False, "reason": "no_credentials_or_expired"}

    try:
        resp = requests.get(
            USAGE_ENDPOINT,
            headers={"Authorization": f"Bearer {token}", "anthropic-beta": "oauth-2025-04-20"},
            timeout=TIMEOUT,
        )
    except requests.RequestException:
        return {"available": False, "reason": "network_error"}

    if resp.status_code == 429:
        return {"available": False, "reason": "rate_limited"}
    if not resp.ok:
        return {"available": False, "reason": "http_error"}

    try:
        data = resp.json()
    except ValueError:
        return {"available": False, "reason": "bad_response"}

    five_hour = _window(data.get("five_hour"))
    seven_day = _window(data.get("seven_day"))
    if five_hour is None and seven_day is None:
        return {"available": False, "reason": "unexpected_shape"}

    return {"available": True, "five_hour": five_hour, "seven_day": seven_day}
