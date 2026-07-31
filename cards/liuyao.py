"""摇卦卡：`python3 cli.py push liuyao` 或被签筒/NFC 路由调用。

每次调用真实抛一卦（`secrets` 而非 `random`，见 providers/liuyao.py），
不缓存、不复用上一次结果——摇卦这个动作本身的仪式感就在于"每次都是新的"。
"""
from providers.liuyao import cast_hexagram
from render.base import to_data_url
from render.divination import render


def build() -> dict:
    cast = cast_hexagram()
    img = render(cast)
    title = cast["本卦"] if not cast["变卦"] else f"{cast['本卦']}→{cast['变卦']}"
    return {
        "png": to_data_url(img),
        "alias": "摇卦",
        "link": "",  # M2 阶段接上 NFC 回调后再填自己的 /t/... URL
        "meta": {"本卦": cast["本卦"], "变卦": cast["变卦"], "判断": cast["判断"]},
    }
