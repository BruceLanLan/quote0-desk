"""屏上宠物：状态语义直接对齐官方 anthropics/claude-desktop-buddy
（sleep/idle/busy/attention/celebrate/heart），不是自己发明的一套
"饥饿值"——用户点名要把宠物这块"融合"进官方项目，这里连状态命名和触发
条件都跟官方源码保持一致，只是把"连续动画 + BLE 实时推送"换成"静态
墨水屏 + 定期/事件触发推送"。

信号源：

- **优先——buddy-bridge**：本机 `~/buddy-bridge` 守护进程在跑，直接用
  它的 `running`/`waiting` 实时信号：`waiting>0` → `attention`；
  `running>0` → `busy`；都没有 → `idle`。这是官方项目本来的信号形状
  （BLE 桥接实时推送 session 状态），buddy-bridge 就是同一协议的本机
  实现。
- **兜底——git commit**：没有 buddy-bridge（公开仓库的大多数使用者都
  没有）就退回扫 `DEFAULT_REPOS` 的最新 commit 时间：commit 在窗口内
  → `idle`；太久没提交 → `sleep`（官方语义是"桥接不在线"，我们没有
  真正的桥接信号时，直接借这个状态名而不是自己发明"饿了/难过"）。
- **celebrate**：`tokens_today` 跨过一个新的 5 万整数关口，跟官方
  "每 50K tokens 升一级"的触发点一致。
- **heart**：NFC 贴一下摸摸（`/t/pet_pat`）。官方语义是"5 秒内被批准
  的奖励反应"，跟"被摸摸"是同一种"我很开心"，共用一个状态；以后接上
  "贴一下批准工具调用"功能时，快速批准也会触发这个状态，不用新增素材。

没有移植的官方状态：`dizzy`（原触发条件是摇晃设备的加速度计读数，
Quote/0 没有加速度计，没有对应的物理动作可以触发）。
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime

from providers.buddy import fetch as fetch_buddy

STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pet_state.json")

DEFAULT_REPOS = [
    os.path.expanduser("~/dev/quote0-desk"),
    os.path.expanduser("~/dev/pocket-prophet-dashboard"),
]

SPECIES = "duck"  # v1 先固定一种造型，选宠物是后续功能，不在这次范围内

IDLE_WINDOW_HOURS = 6  # 没有 buddy-bridge 时，多久没提交就当"没连上"（sleep）
HEART_GLOW_SECONDS = 600  # 摸摸之后 heart 状态维持多久
CELEBRATE_GLOW_SECONDS = 900  # 里程碑庆祝维持多久
CELEBRATE_STEP_TOKENS = 50_000  # 跟官方一致：每 50K tokens 一个里程碑


def _load() -> dict:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save(state: dict):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _latest_commit_ts(repo: str) -> float | None:
    try:
        out = subprocess.run(
            ["git", "-C", repo, "log", "-1", "--format=%ct"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return float(out) if out else None
    except (subprocess.SubprocessError, OSError, ValueError):
        return None


def _latest_commit_across(repos: list[str]) -> float | None:
    timestamps = [t for t in (_latest_commit_ts(r) for r in repos) if t is not None]
    return max(timestamps) if timestamps else None


def scan(repos: list[str] = None) -> dict:
    """推进一次状态判定，返回渲染需要的全部字段。这个函数本身会读写
    状态文件，调用一次就会推进一次时间——不是纯查询。
    """
    repos = repos or DEFAULT_REPOS
    raw = _load()
    now = time.time()

    last_active_ts = raw.get("last_active_ts", now)
    last_seen_commit_ts = raw.get("last_seen_commit_ts", 0)
    last_pat_ts = raw.get("last_pat_ts", 0)
    last_celebrated_milestone = raw.get("last_celebrated_milestone", 0)
    celebrate_started_ts = raw.get("celebrate_started_ts", 0)

    buddy = fetch_buddy()

    if buddy.get("available"):
        waiting = buddy.get("waiting", 0) > 0
        running = buddy.get("running", 0) > 0
        base_state = "attention" if waiting else ("busy" if running else "idle")
        last_active_ts = now
    else:
        waiting = False
        latest_commit = _latest_commit_across(repos)
        if latest_commit is not None and latest_commit > last_seen_commit_ts:
            last_seen_commit_ts = latest_commit
            last_active_ts = now
        hours_idle = max(0.0, (now - last_active_ts) / 3600)
        base_state = "sleep" if hours_idle > IDLE_WINDOW_HOURS else "idle"

    tokens_today = buddy.get("tokens_today", 0) if buddy.get("available") else 0
    milestone = tokens_today // CELEBRATE_STEP_TOKENS
    if milestone > last_celebrated_milestone:
        last_celebrated_milestone = milestone
        celebrate_started_ts = now

    celebrating = bool(celebrate_started_ts) and (now - celebrate_started_ts) < CELEBRATE_GLOW_SECONDS
    hearting = bool(last_pat_ts) and (now - last_pat_ts) < HEART_GLOW_SECONDS

    if waiting:
        display_state = "attention"
    elif celebrating:
        display_state = "celebrate"
    elif hearting:
        display_state = "heart"
    else:
        display_state = base_state

    species = raw.get("species", SPECIES)
    _save({
        "species": species,
        "last_active_ts": last_active_ts,
        "last_seen_commit_ts": last_seen_commit_ts,
        "last_pat_ts": last_pat_ts,
        "last_celebrated_milestone": last_celebrated_milestone,
        "celebrate_started_ts": celebrate_started_ts,
    })

    return {
        "species": species,
        "state": display_state,
        "frame_index": int(now // 5) % 3,
        "last_active_label": datetime.fromtimestamp(last_active_ts).strftime("%m-%d %H:%M"),
    }


def pat() -> dict:
    """NFC 贴一下：摸摸它，触发 heart 状态一段时间。"""
    raw = _load()
    raw["last_pat_ts"] = time.time()
    _save(raw)
    return scan()
