"""状态板：贴一下不算数，靠对话往上面写。

**D5（本轮设计决策）：这张卡的每一行只能由对话写入，禁止任何 provider
定时轮询填充。** 如果某一行的内容可以由 provider 抓出来，那它就是仪表盘行，
不属于这张卡，应该另开一张卡或塞进已有的信息类卡片——这条线是本轮唯一
一条可以在 code review 时机械检查的产品约束（"这个值是不是从某个
`fetch()`/`scan()` 来的？是的话就不该写进这里"）。

跟 `providers/hermes_inbox.py` 同一套纪律：只存当前态、有硬上限、读失败
返回 None 不抛异常。区别是这里是多行（最多 `MAX_ROWS` 条），
`hermes_inbox` 只有一条。

不做历史/翻页——这张卡只有"现在"，没有"昨天"，跟 `providers/todo.py`、
`providers/pet.py` 明确回避"连续打卡"式 streak 是同一个判断。
"""
from __future__ import annotations

import json
import os
import time

from render.rows import MAX_ROWS

STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "agent_board.json")

LABEL_MAX_LEN = 6  # 渲染层还有 truncate_to_width 兜底，这里只是存储层的粗略限长
VALUE_MAX_LEN = 20


def _load() -> dict:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"rows": []}


def _save(state: dict):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def set_row(label: str, value: str) -> dict:
    """写一行——同名 label 覆盖上一次的内容（连同时间戳一起更新），新
    label 追加到末尾；超过 `MAX_ROWS` 行时挤掉最旧的一行（按最后更新
    时间排序，不是按 label 字母序）。空 label 直接拒绝，不静默存一条
    没有名字的记录。
    """
    label = str(label or "").strip()[:LABEL_MAX_LEN]
    value = str(value or "").strip()[:VALUE_MAX_LEN]
    if not label:
        raise ValueError("label 不能为空")

    state = _load()
    rows = [r for r in state.get("rows", []) if r.get("label") != label]
    rows.append({"label": label, "value": value, "ts": time.time()})
    if len(rows) > MAX_ROWS:
        rows.sort(key=lambda r: r.get("ts", 0))
        rows = rows[-MAX_ROWS:]

    state = {"rows": rows}
    _save(state)
    return state


def drop_row(label: str) -> dict:
    state = _load()
    rows = [r for r in state.get("rows", []) if r.get("label") != label]
    state = {"rows": rows}
    _save(state)
    return state


def clear() -> dict:
    state = {"rows": []}
    _save(state)
    return state


def board() -> dict | None:
    """只读查看，不推进任何状态。返回 `None` 代表"从来没写过"，跟"写过
    但清空了"是两种不同的状态，卡片渲染时分别处理成不同的提示文案。"""
    if not os.path.exists(STATE_PATH):
        return None
    return _load()
