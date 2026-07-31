"""今日一件事：本地 JSON 存今天的承诺，NFC 打卡标记完成。

数据模型故意简单——一天只认一件事，过了午夜自动认为"新的一天，旧的作废"，
不做历史记录/连续打卡这类功能（那是另一个产品，不是这张卡的范围）。
"""
import json
import os
from datetime import date

STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "todo.json")


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


def get_today() -> dict:
    """返回 {"date": "...", "task": "...", "done": bool}。跨天且没设新任务
    时 task 为空字符串——渲染层要处理"今天还没定"这个状态。
    """
    state = _load()
    today = date.today().isoformat()
    if state.get("date") != today:
        return {"date": today, "task": "", "done": False}
    return state


def set_task(task: str):
    _save({"date": date.today().isoformat(), "task": task, "done": False})


def toggle_done() -> dict:
    """NFC 打卡：切换今天这件事的完成状态。若今天还没设任务，打卡是 no-op。"""
    today = get_today()
    if not today["task"]:
        return today
    today["done"] = not today["done"]
    _save(today)
    return today
