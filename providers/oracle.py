"""应期复盘：摇一卦时记下问的是什么，到应期日自动提醒"应了吗"，记录历史
命中率——这是本项目玄学方向唯一一个"只有这块屏能成立"的功能：手机上问 AI
也能起一卦，但"过些天再回来问你当初问的事应验了没有"这种主动的、跨越
时间的追问，只有一块常驻的屏幕才做得到。

对话式起卦（MCP `cast_with_question(question)`）跟贴 NFC 摇卦
（`cards/liuyao.py`）是两条独立的路：这条记问题、记应期，那条不记，
各自成立，不互相依赖，不重写起卦算法——照样调 `providers/liuyao.py`
的 `cast_hexagram()`。

跟 `providers/agent_board.py` 同一套纪律：只存需要的状态、有硬上限
（`MAX_ENTRIES`），读失败返回空列表不抛异常。
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime

import config
import scheduler
from providers.liuyao import cast_hexagram

LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "oracle_log.json")

MAX_ENTRIES = 50
QUESTION_MAX_LEN = 60


def _load() -> list:
    if os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save(entries: list):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def cast(question: str, review_days: int | None = None) -> tuple[dict, dict]:
    """起一卦并记下问题，返回 `(entry, full_cast)`：`entry` 是存进日志的
    简化记录，`full_cast` 是 `cast_hexagram()` 的完整原始结果（含
    `lines`/`动爻`等渲染爻线图需要的字段，不落盘）。**调用方渲染屏幕时
    必须用这个 `full_cast`，不能重新调一次 `cast_hexagram()`**——那样
    随机结果会跟日志里记的对不上，屏幕显示的卦和"应期复盘"以后回看的
    卦就变成两回事了。`review_days` 不传时读 `config.json` 的
    `oracle_review_days`（默认 7），跟 `pomodoro_minutes` 同一个模式。
    """
    question = str(question or "").strip()[:QUESTION_MAX_LEN]
    if review_days is None:
        review_days = int(config.load().get("oracle_review_days", 7) or 7)
    full_cast = cast_hexagram()
    now = time.time()
    entry = {
        "question": question,
        "hexagram": full_cast["本卦"],
        "changed_hexagram": full_cast.get("变卦"),
        "reading": full_cast.get("判断", ""),
        "cast_at": now,
        "review_at": now + max(1, int(review_days)) * 86400,
        "verdict": None,  # None=未回看，"yes"/"no"=已回看
        "notified_at": None,
    }
    entries = _load()
    entries.append(entry)
    if len(entries) > MAX_ENTRIES:
        entries = entries[-MAX_ENTRIES:]
    _save(entries)
    return entry, full_cast


def _find_due(entries: list, now: float):
    """找一条到了应期日但还没回看过的记录——只找最早到期的一条，一次
    只提醒一件事，不会因为攒了好几条一起炸出来。"""
    due = [e for e in entries if e.get("verdict") is None and e.get("review_at", float("inf")) <= now]
    if not due:
        return None
    due.sort(key=lambda e: e["review_at"])
    return due[0]


def check_due() -> dict | None:
    """由 scheduler 的 watcher 定期调用，也给卡片渲染直接用。返回到期
    的那条记录，没有到期的返回 None。这个函数本身**不会**把状态标记成
    "已提醒"——应期复盘卡可能被自主轮转再次覆盖，需要能重复渲染同一条
    到期记录，直到用户用 `verdict()` 明确回答，这条记录才算翻篇。
    """
    return _find_due(_load(), time.time())


def verdict(answer: str) -> dict | None:
    """回答"应了吗"——找最早到期且还没回答的那一条标记 verdict，返回
    这条记录；没有待回答的记录时返回 None。"""
    entries = _load()
    due = _find_due(entries, time.time())
    if due is None:
        return None
    due["verdict"] = answer
    _save(entries)
    return due


def stats() -> dict:
    """历史命中率：只统计已经回看过的条目。"""
    entries = _load()
    answered = [e for e in entries if e.get("verdict") in ("yes", "no")]
    hits = sum(1 for e in answered if e["verdict"] == "yes")
    return {"total": len(answered), "hits": hits}


def _watch():
    """只在"刚到期、还没通知过"时插队推送一次——不能像 check_due() 那样
    每次调度线程醒来（约 5 秒一次）就无脑判断"有没有到期"，那样同一条
    记录会被反复插队推送，用户回答之前屏幕会一直被打断。用 `notified_at`
    字段区分"已经通知过、等用户回应"和"刚到期、第一次发现"，只在后一种
    情况才触发插队；已经通知过的记录仍然可以被主动 push 看到（渲染层的
    `check_due()` 不受这个字段影响），只是不会被 watcher 反复打扰。
    """
    entries = _load()
    due = _find_due(entries, time.time())
    if due is None or due.get("notified_at"):
        return
    due["notified_at"] = time.time()
    _save(entries)
    # request_push_urgent()：不受布防开关约束，跟 providers/pomodoro.py
    # 同一个论证——用户开口问了一卦，就是明确意图，应期到了的提醒不该
    # 被一个不相关的自动轮换开关（默认关闭）吞掉。
    scheduler.request_push_urgent("oracle_review")


scheduler.register_watcher(_watch)
