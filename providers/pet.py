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
  没有）就退回扫 `config.json` 里 `pet_repos` 列出的仓库（控制台设置页
  可改，默认是这个项目自己 + pocket-prophet-dashboard）的最新 commit
  时间：commit 在窗口内
  → `idle`；太久没提交 → `sleep`（官方语义是"桥接不在线"，我们没有
  真正的桥接信号时，直接借这个状态名而不是自己发明"饿了/难过"）。
- **celebrate**：`tokens_today` 跨过一个新的 5 万整数关口，跟官方
  "每 50K tokens 升一级"的触发点一致。
- **heart**：NFC 贴一下摸摸（`/t/pet_pat`）。官方语义是"5 秒内被批准
  的奖励反应"，跟"被摸摸"是同一种"我很开心"，共用一个状态；以后接上
  "贴一下批准工具调用"功能时，快速批准也会触发这个状态，不用新增素材。

没有移植的官方状态：`dizzy`（原触发条件是摇晃设备的加速度计读数，
Quote/0 没有加速度计，没有对应的物理动作可以触发）。

**waiting 超时告警**：`waiting>0` 一进入就是 attention 状态（见上），
但刚开始等待和已经等了很久，紧迫程度不一样——冰箱贴不该跟第一秒就喊
"快来批准"一样吵。`waiting_since_ts` 记录这次等待从什么时候开始，超过
`WAITING_ALERT_MINUTES` 才把 buddy-bridge 的 `msg`（正在等待的具体
工具调用）显示到卡面上，见 `render/pet.py`。等待结束（`waiting`
重新变 False）立刻清零，不会跨会话残留上一次的告警。

**造型**：官方 18 种里移植了 7 种，见 `render/pet_sprites.py`；选哪一种由
`config.json` 的 `pet_species` 决定（控制台设置页有下拉框），默认鸭子。
判定「活跃 / 在跑 / 等审批」的那一段逻辑跟状态灯卡共用
`providers/buddy.py` 的 `base_state()`，两张卡不会各自漂移。
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime

import config
from providers import buddy as buddy_provider
from render.pet_sprites import DEFAULT_SPECIES, is_valid_species

STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pet_state.json")

IDLE_WINDOW_HOURS = 6  # 没有 buddy-bridge 时，多久没提交就当"没连上"（sleep）
HEART_GLOW_SECONDS = 600  # 摸摸之后 heart 状态维持多久
CELEBRATE_GLOW_SECONDS = 900  # 里程碑庆祝维持多久
CELEBRATE_STEP_TOKENS = 50_000  # 跟官方一致：每 50K tokens 一个里程碑
WAITING_ALERT_MINUTES = 5  # 等待超过这个时长才升级成"点名工具"的告警


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


def current_species() -> str:
    """当前造型：以 `config.json` 的 `pet_species` 为准，非法/没配退回鸭子。

    **不读 `data/pet_state.json`**——早期版本把 species 也写进状态文件、读的时候
    优先取状态文件，结果是用户在设置页换了造型，状态文件里那份旧值会一直盖住
    新配置，永远显示鸭子。配置是唯一权威，状态文件只存"时间戳类"的运行时状态。
    """
    species = str(config.load().get("pet_species") or "").strip()
    return species if is_valid_species(species) else DEFAULT_SPECIES


def scan(repos: list[str] = None) -> dict:
    """推进一次状态判定，返回渲染需要的全部字段。这个函数本身会读写
    状态文件，调用一次就会推进一次时间——不是纯查询。
    """
    repos = repos or config.path_list_setting("pet_repos")
    raw = _load()
    now = time.time()

    last_active_ts = raw.get("last_active_ts", now)
    last_seen_commit_ts = raw.get("last_seen_commit_ts", 0)
    last_pat_ts = raw.get("last_pat_ts", 0)
    last_celebrated_milestone = raw.get("last_celebrated_milestone", 0)
    celebrate_started_ts = raw.get("celebrate_started_ts", 0)
    waiting_since_ts = raw.get("waiting_since_ts", 0)

    buddy = buddy_provider.fetch()
    # 判定逻辑跟状态灯卡共用 providers/buddy.py 的这一份，两边不各写一遍。
    base_state = buddy_provider.base_state(buddy)

    if base_state is not None:
        waiting = base_state == "attention"
        last_active_ts = now
        if waiting:
            waiting_since_ts = waiting_since_ts or now
        else:
            waiting_since_ts = 0
    else:
        waiting = False
        waiting_since_ts = 0
        latest_commit = _latest_commit_across(repos)
        if latest_commit is not None and latest_commit > last_seen_commit_ts:
            last_seen_commit_ts = latest_commit
            last_active_ts = now
        hours_idle = max(0.0, (now - last_active_ts) / 3600)
        base_state = "sleep" if hours_idle > IDLE_WINDOW_HOURS else "idle"

    waiting_minutes = int((now - waiting_since_ts) / 60) if waiting_since_ts else 0
    waiting_alert = waiting and waiting_minutes >= WAITING_ALERT_MINUTES

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

    species = current_species()
    _save({
        # species 故意不写进状态文件——见 current_species() 的说明，配置是唯一
        # 权威，状态文件里存一份副本只会在用户换造型时反过来盖住新配置。
        "last_active_ts": last_active_ts,
        "last_seen_commit_ts": last_seen_commit_ts,
        "last_pat_ts": last_pat_ts,
        "last_celebrated_milestone": last_celebrated_milestone,
        "celebrate_started_ts": celebrate_started_ts,
        "waiting_since_ts": waiting_since_ts,
    })

    return {
        "species": species,
        "state": display_state,
        "frame_index": int(now // 5) % 3,
        "last_active_label": datetime.fromtimestamp(last_active_ts).strftime("%m-%d %H:%M"),
        "waiting_alert": waiting_alert,
        "waiting_minutes": waiting_minutes,
        "waiting_tool": buddy.get("msg", "") if waiting_alert else "",
    }


def pat() -> dict:
    """NFC 贴一下：摸摸它，触发 heart 状态一段时间。"""
    raw = _load()
    raw["last_pat_ts"] = time.time()
    _save(raw)
    return scan()
