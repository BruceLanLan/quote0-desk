"""箴言机：从种子缓存里挑一句，不调用任何模型 API。

用户 2026-07-31 明确选择"先写种子缓存"而不是接模型生成——成本闸的教训是
"不能每次刷屏都调模型"，种子缓存直接把这条风险归零。真要接生成式内容，
以后要么手动扩充 `data/proverbs_seed.json`，要么接一个明确点名的模型通道
（见计划文档），不是这次顺手加的事。

`secrets` 洗牌 + 顺序发放，保证一轮里不重复，比"每次纯随机"更不容易连续
撞到同一句。"""
from __future__ import annotations

import json
import os
import secrets

SEED_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "proverbs_seed.json")
STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "proverb_state.json")


def _load_seed() -> list[str]:
    with open(SEED_PATH) as f:
        return json.load(f)


def _load_state() -> dict:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_state(state: dict):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, ensure_ascii=False)


def _ensure_shuffled(state: dict, seed: list[str]) -> dict:
    order = state.get("order")
    pos = state.get("pos", 0)
    if not order or pos >= len(order) or set(order) != set(seed):
        order = list(seed)
        secrets.SystemRandom().shuffle(order)
        pos = 0
    return {"order": order, "pos": pos}


def current() -> str:
    seed = _load_seed()
    state = _ensure_shuffled(_load_state(), seed)
    _save_state(state)
    return state["order"][state["pos"]]


def advance() -> str:
    """NFC「换一句」：翻到下一条，见底就重新洗牌。"""
    seed = _load_seed()
    state = _ensure_shuffled(_load_state(), seed)
    state["pos"] += 1
    if state["pos"] >= len(state["order"]):
        order = list(seed)
        secrets.SystemRandom().shuffle(order)
        state = {"order": order, "pos": 0}
    _save_state(state)
    return state["order"][state["pos"]]
