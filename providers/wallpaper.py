"""换壁纸：用户从控制台上传一张任意图片，转成 296×152 黑白抖动图存起来，
之后 `push wallpaper` 推的就是这张；没上传过就用 `render/wallpaper.py`
生成的默认"八方来财"图。

上传的图片是用户自己的数据，不落进仓库——`data/wallpaper_custom.png`
已经在 `.gitignore` 里，跟其它 `data/*.json` 状态文件同一条纪律。

转换步骤（PIL 一条链）：
1. 按"覆盖"策略缩放到能填满 296×152（保持宽高比，多出来的部分居中裁掉）
   ——不是拉伸变形，也不是留白，用户传的照片主体不会被压扁
2. 转灰度再转 1-bit，`Image.FLOYDSTEINBERG` 抖动——纯黑白二值图直接转
   （不抖动）大面积渐变会变成一块块死黑/死白，抖动能让过渡看起来还有
   层次，这块屏幕的老式黑白特性下抖动效果反而是"复古"而不是"糊"
"""
from __future__ import annotations

import os

from PIL import Image

from render.base import HEIGHT, WIDTH
from render.wallpaper import default_wallpaper

CUSTOM_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "wallpaper_custom.png")

MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8MB，够任何手机随手拍的照片，防止有人传一张离谱大的图拖垮转换


def _fit_and_dither(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    src_w, src_h = img.size
    target_ratio = WIDTH / HEIGHT
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        # 原图更"宽"，按高对齐，裁掉左右多出来的部分
        new_h = HEIGHT
        new_w = int(src_w * (HEIGHT / src_h))
    else:
        new_w = WIDTH
        new_h = int(src_h * (WIDTH / src_w))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - WIDTH) // 2
    top = (new_h - HEIGHT) // 2
    img = img.crop((left, top, left + WIDTH, top + HEIGHT))
    img = img.convert("L").convert("1", dither=Image.FLOYDSTEINBERG)
    return img.convert("RGB")


def save_upload(file_bytes: bytes) -> dict:
    """存一张新壁纸。成功返回 `{"ok": True}`，失败（不是图片/超限）返回
    `{"ok": False, "hint": ...}`，路由层直接透传，不抛异常。"""
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        return {"ok": False, "hint": f"图片太大（上限 {MAX_UPLOAD_BYTES // 1024 // 1024}MB）"}
    try:
        import io
        img = Image.open(io.BytesIO(file_bytes))
        img.load()  # 提前触发解码失败，不要拖到 convert 阶段才报错
    except Exception:
        return {"ok": False, "hint": "不是有效的图片文件"}

    out = _fit_and_dither(img)
    os.makedirs(os.path.dirname(CUSTOM_PATH), exist_ok=True)
    out.save(CUSTOM_PATH)
    return {"ok": True}


def has_custom() -> bool:
    return os.path.exists(CUSTOM_PATH)


def reset() -> None:
    if os.path.exists(CUSTOM_PATH):
        os.remove(CUSTOM_PATH)


def current() -> Image.Image:
    if has_custom():
        try:
            img = Image.open(CUSTOM_PATH)
            img.load()
            return img.convert("RGB")
        except Exception:
            pass  # 存的文件损坏了，退回默认图，不让整张卡挂掉
    return default_wallpaper()
