"""屏上宠物：状态由真实行为驱动，不是手点喂食。

- **优先信号——buddy-bridge**：如果本机在跑 `~/buddy-bridge`（另一个本机
  项目，用 Claude Code hook 实时上报会话状态），直接读它的 `running`/
  `waiting` 字段——真在干活 = 喂食，等审批 = 一个新的"等待"表情。这比
  "扫两个仓库的 git commit 时间"准得多，commit 只在提交那一刻才有信号，
  buddy-bridge 是连续的。
- **兜底信号——commit**：buddy-bridge 没在跑（公开仓库的其他使用者大概率
  没有这个守护进程）就退回原来的逻辑：`DEFAULT_REPOS` 里出现比上次记录
  更新的 commit，判定为"喂过了"，饥饿清零。
- **长时间没有任何信号 = 饿**：饥饿值按距上次喂食的真实小时数线性增长。
- **NFC 贴一下 = 摸摸**：不影响饥饿，只给一次性的"精神"反应（眼神变化 +
  一句话），持续到下次 scan 判定超时为止——这是即时互动，跟"喂食"这个
  需要真实行为的动作分开，别把两件事混成一件事。

没有做"测试跑挂 = 不高兴"：要在任意仓库里可靠感知测试失败，得在每个项目
装 hook，这已经超出这张卡本身的范围，先不做，需要再拉出来单独设计。
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

HUNGER_PER_HOUR = 6  # 饥饿值增速：约 16.7 小时不喂食到满
PAT_GLOW_SECONDS = 600  # 摸摸之后"精神"反应维持多久，过了就回归按饥饿值判断的心情


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


def _mood_from_hunger(hunger: float) -> str:
    if hunger < 25:
        return "happy"
    if hunger < 60:
        return "neutral"
    if hunger < 90:
        return "hungry"
    return "sad"


def scan(repos: list[str] = None) -> dict:
    """按真实经过时间推进饥饿值，检测新 commit 就喂食，返回渲染需要的全部
    字段。这个函数本身会读写状态文件，调用一次就会推进一次时间——不是纯
    查询，是"喂时间给宠物"的那个动作。
    """
    repos = repos or DEFAULT_REPOS
    state = _load()
    now = time.time()

    last_fed_ts = state.get("last_fed_ts", now)
    last_seen_commit_ts = state.get("last_seen_commit_ts", 0)
    hunger = state.get("hunger", 20)
    last_pat_ts = state.get("last_pat_ts", 0)

    buddy = fetch_buddy()
    buddy_working = buddy.get("available") and buddy.get("running", 0) > 0
    buddy_waiting = buddy.get("available") and buddy.get("waiting", 0) > 0

    latest_commit = _latest_commit_across(repos)
    fed_by_commit = latest_commit is not None and latest_commit > last_seen_commit_ts
    fed_just_now = fed_by_commit or buddy_working
    if fed_by_commit:
        last_seen_commit_ts = latest_commit
    if fed_just_now:
        last_fed_ts = now
        hunger = 0
    else:
        hours_since_fed = max(0.0, (now - last_fed_ts) / 3600)
        hunger = min(100.0, hours_since_fed * HUNGER_PER_HOUR)

    state = {
        "species": state.get("species", SPECIES),
        "hunger": hunger,
        "last_fed_ts": last_fed_ts,
        "last_seen_commit_ts": last_seen_commit_ts,
        "last_pat_ts": last_pat_ts,
    }
    _save(state)

    patted_recently = (now - last_pat_ts) < PAT_GLOW_SECONDS
    if buddy_waiting:
        mood = "waiting"  # 一个操作在等审批，跟饥饿状态无关，优先显示
    elif patted_recently:
        mood = "alert"
    else:
        mood = _mood_from_hunger(hunger)

    return {
        "species": state["species"],
        "hunger": round(hunger),
        "mood": mood,
        "fed_just_now": fed_just_now,
        "frame_index": int(now // 5) % 3,
        "last_fed_label": datetime.fromtimestamp(last_fed_ts).strftime("%m-%d %H:%M"),
    }


def pat() -> dict:
    """NFC 贴一下：摸摸它，触发一次性的"精神"反应，不改变饥饿值。"""
    state = _load()
    state["last_pat_ts"] = time.time()
    if "hunger" not in state:
        state["hunger"] = 20
    _save(state)
    return scan()
