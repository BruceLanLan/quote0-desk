"""签筒：NFC 贴一下抽一签，`secrets` 真随机在摇卦/奇门遁甲之间二选一。

计划里签筒的另一种形态（把官方 loop 槽本身当抽签，靠 /next 换到下一项）
留到 M2 NFC 闭环打通、能实际测 /next 跟 refreshNow 推送的交互效果时再定，
这里先实现"贴一下→真随机起一卦或起一盘→推上屏"这个更直接可控的版本。
"""
import secrets

from cards import liuyao, qimen
from config import nfc_base_url


def build() -> dict:
    which = secrets.choice([liuyao, qimen])
    result = which.build()
    result["alias"] = f"签筒·{result['alias']}"
    base = nfc_base_url()
    result["link"] = f"{base}/t/qiantong" if base else ""
    return result
