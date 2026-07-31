"""屏上宠物卡：状态由 providers/pet.py 的真实行为（commit/时间流逝）驱动，
NFC 贴一下走 /t/pet_pat 摸摸它（见 server.py），不是随便点点就喂饱。"""
from providers.pet import scan
from render.base import to_data_url
from render.pet import render


def build() -> dict:
    state = scan()
    img = render(state)
    return {
        "png": to_data_url(img),
        "alias": "屏上宠物",
        "link": "",  # M6 接上服务公网地址后填 /t/pet_pat
    }
