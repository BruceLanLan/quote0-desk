"""quote0-desk 的 MCP server：把具体的内容卡片暴露成 Claude 能直接调用的
工具（摇一卦、摸摸宠物、设今日任务……），不是又一个通用文本/图片透传——
那个方向已经有至少 4 个独立实现在做了（README「全部内容卡」附近有链接），
重复没有意义，这里的差异化就是"工具即卡片"。

跟 quote0-desk 主项目（`server.py` 的 Flask 控制台/NFC 回调）是完全独立的
进程：这个 MCP server 只是通过 HTTP 调用主项目已经在跑的 `/api/*` 接口，
不直接 import 卡片/provider 代码。这样做的直接原因是 Python 版本——
`mcp` SDK 要求 3.10+，主项目为了跟这台机器上已装好的依赖兼容，一直走
系统自带的 3.9，两边不用互相迁就对方的版本。

前提：quote0-desk 的 `server.py` 得已经在跑（默认
`http://localhost:5252`，可用 `QUOTE0_DESK_URL` 环境变量覆盖）。这个
MCP server 只是它的客户端，不会在它没启动时自己去拉起。
"""
from __future__ import annotations

import os

import requests
from mcp.server import MCPServer

BASE_URL = os.environ.get("QUOTE0_DESK_URL", "http://localhost:5252").rstrip("/")
TIMEOUT = 15  # 推送要等 Dot 云 API 走一圈，比本地调用宽松一点

mcp = MCPServer("quote0-desk")


def _request(method: str, path: str, body: dict | None = None, **params) -> dict:
    try:
        r = requests.request(method, f"{BASE_URL}{path}", json=body, params=params, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise RuntimeError(
            f"连不上 quote0-desk（{BASE_URL}）：先确认 python3 server.py 有没有在跑。原始错误：{e}"
        ) from e
    r.raise_for_status()
    return r.json()


def _get(path: str, **params) -> dict:
    return _request("GET", path, **params)


def _post(path: str, body: dict | None = None, **params) -> dict:
    return _request("POST", path, body=body, **params)


def _push_summary(card: str, result: dict) -> str:
    if not result.get("ok"):
        return f"推送失败：{result.get('hint', '未知错误')}"
    push = result.get("push", {})
    if push.get("ok"):
        return f"已推送「{card}」到 Quote/0 屏幕"
    return f"推送失败：{push.get('hint', '未知错误')}"


@mcp.tool()
def push_pet() -> str:
    """把屏上宠物卡推到 Quote/0：ASCII 造型，状态反映真实的 Claude Code
    活动信号（对齐官方 claude-desktop-buddy 的 sleep/idle/busy/attention/
    celebrate/heart）。"""
    return _push_summary("pet", _post("/api/push", card="pet"))


@mcp.tool()
def pat_pet() -> str:
    """摸摸屏上的宠物：触发一次性的开心（heart）反应并立刻推回屏幕，
    等价于真实贴一次 NFC。"""
    r = _get("/t/pet_pat")
    ok = r.get("push", {}).get("ok")
    return "已摸摸宠物，屏幕已更新" if ok else f"失败：{r}"


@mcp.tool()
def draw_hexagram() -> str:
    """摇一卦（六爻），用 `secrets` 真随机抛铜钱起卦，推到 Quote/0 屏幕。"""
    return _push_summary("liuyao", _post("/api/push", card="liuyao"))


@mcp.tool()
def cast_qimen() -> str:
    """按当前时间起一盘奇门遁甲，推到 Quote/0 屏幕。"""
    return _push_summary("qimen", _post("/api/push", card="qimen"))


@mcp.tool()
def draw_qiantong() -> str:
    """抽签筒：摇卦或奇门二选一，`secrets` 真随机，推到 Quote/0 屏幕。"""
    return _push_summary("qiantong", _post("/api/push", card="qiantong"))


@mcp.tool()
def push_daily() -> str:
    """把日课卡推到 Quote/0：当前时刻的四柱干支（年月日时）+ 日干五行。"""
    return _push_summary("daily", _post("/api/push", card="daily"))


@mcp.tool()
def push_proverb() -> str:
    """把桌面箴言机卡推到 Quote/0：当前这一句箴言。"""
    return _push_summary("proverb", _post("/api/push", card="proverb"))


@mcp.tool()
def push_status() -> str:
    """把 Claude Code 状态灯卡推到 Quote/0：账号配额/今日用量 + 活跃指示。"""
    return _push_summary("status", _post("/api/push", card="status"))


@mcp.tool()
def set_today_task(task: str) -> str:
    """设置「今日一件事」并立刻推到 Quote/0 屏幕。"""
    r = _post("/api/todo", body={"task": task})
    if not r.get("ok"):
        return f"设置失败：{r.get('hint', '未知错误')}"
    return f"已设置今日任务「{task}」并推送到屏幕"


@mcp.tool()
def toggle_today_task() -> str:
    """切换「今日一件事」的完成状态（打卡/撤销打卡），立刻推到 Quote/0 屏幕。"""
    r = _get("/t/todo_toggle")
    state = r.get("state", {})
    done = state.get("done")
    if done is None:
        return f"切换失败：{r}"
    return f"今日任务「{state.get('task', '')}」已标记为{'完成' if done else '未完成'}"


@mcp.tool()
def board_note(label: str, value: str) -> str:
    """在 Quote/0 的状态板上记一行，立刻推到屏幕。label 是这件事的名字
    （不超过 6 个字，同名会覆盖上一次的记录而不是新增一行——比如再记一次
    「读书」会更新原来那行，不是长出第二行），value 是这次的具体内容
    （不超过 20 个字）。板子最多同时显示 5 行，写第 6 件事时最早的一行
    会被自动挤掉。这张卡只反映"你刚才告诉我的事"，不会自己去抓任何数据——
    如果信息不全（比如只说"记一下喝奶"没说多少毫升），应该先问清楚再调用
    这个工具，不要自己编一个数字。"""
    r = _post("/api/board/row", body={"label": label, "value": value})
    if not r.get("ok"):
        return f"记录失败：{r.get('hint', '未知错误')}"
    return f"已记下「{label}：{value}」并推送到屏幕"


@mcp.tool()
def push_hermes() -> str:
    """把 Hermes 任务台卡推到 Quote/0：本机 hermes-agent gateway 的定时任务
    概览（名字+schedule）。gateway 没在跑或没配 HERMES_API_KEY 时，卡片会
    优雅显示"未接入"，这是可选集成，不是每个人都装了 hermes-agent。"""
    return _push_summary("hermes", _post("/api/push", card="hermes"))


@mcp.tool()
def get_device_status() -> str:
    """只读查看 Quote/0 设备在线状态（电量/WiFi/当前屏幕渲染图 URL）。"""
    r = _get("/api/status")
    if not r.get("ok"):
        return f"获取失败：{r.get('hint', '未知错误')}"
    s = r["status"]["status"]
    return f"{s['current']} · 电量 {s['battery']} · WiFi {s['wifi']}"


@mcp.tool()
def list_cards() -> str:
    """列出 quote0-desk 全部内容卡的名字，方便知道还有哪些可以推送。"""
    r = _get("/api/cards")
    return "、".join(f"{v}（{k}）" for k, v in r.items())


if __name__ == "__main__":
    mcp.run()
