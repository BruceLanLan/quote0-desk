"""奇门遁甲卡：按当前时间起盘，`python3 cli.py push qimen` 或被签筒调用。"""
from providers.qimen import cast
from render.base import to_data_url
from render.qimen import render


def build() -> dict:
    c = cast()
    img = render(c)
    return {
        "png": to_data_url(img),
        "alias": "奇门遁甲",
        "link": "",
        "meta": {"局": c["ju"], "值符星": c["zhi_fu_star"], "值符宫": c["zhi_fu_gong"]},
    }
