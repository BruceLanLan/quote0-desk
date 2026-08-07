"""壁纸卡：走 Image API，推的是 `providers/wallpaper.py` 存的当前壁纸
（用户上传的图，或者没上传过时的默认"八方来财"图）——本地生成/存储的
就是会被原样推上设备的那份，跟 pet/liuyao 这些 Image API 卡同一个纪律。
"""
from __future__ import annotations

from providers import wallpaper
from render.base import to_data_url


def build() -> dict:
    img = wallpaper.current()
    return {"png": to_data_url(img), "alias": "壁纸", "link": ""}
