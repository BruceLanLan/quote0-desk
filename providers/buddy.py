"""buddy-bridge 本地状态：只读接入用户自己的 Claude Code hook 桥接守护进程
（`~/buddy-bridge`，跟这个项目本身无关的另一个本机基础设施），取真实的
跨会话活动信号——运行中/等待审批/空闲、今日 token 消耗、最近动作日志。
比 `providers/pet.py` 原来那套"扫两个仓库的 git commit 时间"或
`providers/claude_activity.py` 那套"扫本地 JSONL 转录文件"都更准：
buddy-bridge 是靠 Claude Code 的 hook 实时喂数据的，不是事后扫文件猜。

守护进程不一定在跑——这是用户本机的可选基础设施，不是这个项目的硬依赖，
公开仓库的其他使用者大概率没有这个守护进程。拿不到就返回
`available: False`，调用方自己决定怎么降级，绝不能让宠物卡/状态灯卡
因为这个守护进程没开就报错。

协议：`~/buddy-bridge/docs/PROTOCOL_V2.md`。`GET /status` 不带 token
只返回健康检查（`authenticated: false`）；带 `X-Buddy-Token`（读
`~/.buddy-bridge/token`，只读，不落库不打日志，跟 claude_quota.py 对
OAuth token 的处理是同一个纪律）返回完整 snapshot。
"""
from __future__ import annotations

import os

import requests

STATUS_URL = "http://127.0.0.1:49431/status"
TOKEN_PATH = os.path.expanduser("~/.buddy-bridge/token")
TIMEOUT = 3  # 本地守护进程，超时给短一点，别让卡片推送等太久


def _load_token() -> str | None:
    if not os.path.exists(TOKEN_PATH):
        return None
    try:
        with open(TOKEN_PATH) as f:
            token = f.read().strip()
        return token or None
    except OSError:
        return None


def fetch() -> dict:
    """返回：
    `{"available": True, "total": int, "running": int, "waiting": int,
      "tokens_today": int, "msg": str}`
    或
    `{"available": False, "reason": "no_token"|"daemon_not_running"|
      "http_error"|"bad_response"|"unauthenticated"}`。

    永不抛异常——守护进程没开是正常状态，不是错误状态。
    """
    token = _load_token()
    if not token:
        return {"available": False, "reason": "no_token"}

    try:
        resp = requests.get(STATUS_URL, headers={"X-Buddy-Token": token}, timeout=TIMEOUT)
    except requests.RequestException:
        return {"available": False, "reason": "daemon_not_running"}

    if not resp.ok:
        return {"available": False, "reason": "http_error"}

    try:
        data = resp.json()
    except ValueError:
        return {"available": False, "reason": "bad_response"}

    if not data.get("authenticated"):
        return {"available": False, "reason": "unauthenticated"}

    snapshot = data.get("snapshot") or {}
    return {
        "available": True,
        "total": snapshot.get("total", 0),
        "running": snapshot.get("running", 0),
        "waiting": snapshot.get("waiting", 0),
        "tokens_today": snapshot.get("tokens_today", 0),
        "msg": snapshot.get("msg", ""),
    }


def base_state(snapshot: dict) -> str | None:
    """把一份 buddy 快照翻译成官方 claude-desktop-buddy 的基础状态名
    （`attention` / `busy` / `idle`），快照不可用时返回 `None`，让调用方各自
    决定怎么降级（宠物卡退回 git commit 时间，状态灯退回转录文件 mtime）。

    这个函数是 2026-08-04 加的：在此之前 `cards/status.py` 的 `_active()` 和
    `providers/pet.py` 里算 `base_state` 的那几行，是对同一份快照的两套独立
    实现——状态灯只区分"活跃/空闲"，宠物区分 attention/busy/idle，两边改一处
    另一处不会跟着变，迟早漂移成"状态灯说空闲、宠物说在等你批准"。判定逻辑
    收在数据源这一侧只留一份，两张卡都从这里取。

    `celebrate` / `heart` 故意不在这里：那两个状态是宠物自己的里程碑计时器和
    NFC 摸摸驱动的，跟 buddy 快照无关，也不该出现在状态灯上。
    """
    if not snapshot.get("available"):
        return None
    if snapshot.get("waiting", 0) > 0:
        return "attention"
    if snapshot.get("running", 0) > 0:
        return "busy"
    return "idle"


def is_active(snapshot: dict) -> bool | None:
    """"有没有正在发生的事"——`busy`（跑着）和 `attention`（等审批）都算活跃。
    快照不可用返回 `None`（不是 `False`），因为"守护进程没开"跟"确实空闲"是
    两回事，调用方要能区分才好降级。"""
    state = base_state(snapshot)
    return None if state is None else state in ("busy", "attention")
