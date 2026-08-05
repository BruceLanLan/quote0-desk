"""应期复盘卡：到了应期日，由 scheduler 的 watcher 检测到、插队推一张
"回看"卡——问的是什么、得的什么卦、现在该回答"应了吗"。走 Text API
（内容是一段带问题的叙述文字，不是并列的多行表格，不需要 render/rows.py
那条路）。

NFC 贴一下的语义简化说明：Quote/0 一张卡只有一个 `link`，没法像手机
App 那样弹"是/否"两个按钮，所以这里贴一下固定对应"应验了"（yes）这个
更有仪式感的动作——"没应验"这个结果预期主要靠对话里跟 Claude 说
（MCP 的 `oracle_verdict("no")`），这是执行时的简化选择，不是规划本身
就这么设计的，如实记在这里。
"""
from __future__ import annotations

from datetime import datetime

from canvas.template import simple_data
from config import nfc_base_url
from providers import oracle


def build() -> dict:
    due = oracle.check_due()
    st = oracle.stats()
    hit_line = f"至今 {st['total']} 问，{st['hits']} 应" if st["total"] else "还没有历史记录"

    if not due:
        title = "应期复盘"
        message = f"暂无到期的卦\n{hit_line}"
        link = ""
    else:
        days = max(0, int((due["review_at"] - due["cast_at"]) / 86400))
        hexagram = due["hexagram"]
        if due.get("changed_hexagram"):
            hexagram = f"{hexagram}→{due['changed_hexagram']}"
        question = due.get("question") or "（没记问题，只记了卦象）"
        title = f"{days} 天前你问"
        message = f"{question}\n得卦：{hexagram}\n应了吗？\n{hit_line}"
        base = nfc_base_url()
        link = f"{base}/t/oracle_verdict" if base else ""

    data = simple_data(title=title, message=message, footer="quote0-desk · 应期复盘")
    return {"data": data, "alias": "应期复盘", "link": link}
