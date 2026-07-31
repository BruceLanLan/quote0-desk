"""渲染公共原语：296×152 横屏画布、字体、文本截断。

规格来源 docs/DEVICE-FACTS.md（本项目实测确认，不是照搬上个项目）：
- 面板分辨率 296×152，黑白（灰阶层次未最终确认，先按二值设计，关键内容
  一律纯黑，不依赖中间灰度的可辨识度）
- 12px 中文清晰可读，10px 明显发糊——12px 是下限

这套原语跟 pocket-prophet-dashboard/renderer/base.py 同源但不是照搬：
屏幕形状从方屏变横屏，原来的 200×200 坐标系整体不适用，需要重新布局，
只有"用 PIL 画本地图 + 按实际渲染宽度截断"这个方法本身是复用的。
"""
import base64
import io
import os

from PIL import Image, ImageDraw, ImageFont

WIDTH = 296
HEIGHT = 152

BLACK = 0
DARK_GRAY = 96
WHITE = 255

FONT_PATH = "/System/Library/Fonts/STHeiti Medium.ttc"
MONO_FONT_PATH = "/System/Library/Fonts/Menlo.ttc"  # ASCII 宠物造型要求等宽，不能用中文字体画
MIN_FONT_SIZE = 12  # docs/DEVICE-FACTS.md P5：10px 发糊，12px 清晰

_font_cache = {}
_mono_font_cache = {}


def font(size: int) -> ImageFont.FreeTypeFont:
    if size < MIN_FONT_SIZE:
        raise ValueError(f"字号 {size} 低于可读下限 {MIN_FONT_SIZE}px（见 docs/DEVICE-FACTS.md）")
    if size not in _font_cache:
        _font_cache[size] = ImageFont.truetype(FONT_PATH, size)
    return _font_cache[size]


def mono_font(size: int) -> ImageFont.FreeTypeFont:
    """等宽字体，专给 ASCII 宠物造型用——中文字体画拉丁字符不保证等宽，
    画出来爻线以外的 ASCII 美术会走形。"""
    if size not in _mono_font_cache:
        _mono_font_cache[size] = ImageFont.truetype(MONO_FONT_PATH, size)
    return _mono_font_cache[size]


def new_canvas(bg=WHITE) -> Image.Image:
    return Image.new("RGB", (WIDTH, HEIGHT), (bg, bg, bg))


def gray(v: int):
    return (v, v, v)


def truncate_to_width(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: int) -> str:
    """按实际渲染宽度截断（中英文混排字宽不同，不能按字符数算）。"""
    if draw.textlength(text, font=fnt) <= max_width:
        return text
    ellipsis = "…"
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        candidate = text[:mid] + ellipsis
        if draw.textlength(candidate, font=fnt) <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + ellipsis


def hline(draw: ImageDraw.ImageDraw, y: int, x0: int = 8, x1: int = WIDTH - 8, fill=DARK_GRAY):
    draw.line([(x0, y), (x1, y)], fill=gray(fill), width=1)


def vline(draw: ImageDraw.ImageDraw, x: int, y0: int = 8, y1: int = HEIGHT - 8, fill=DARK_GRAY):
    draw.line([(x, y0), (x, y1)], fill=gray(fill), width=1)


def to_data_url(img: Image.Image) -> str:
    """Image API 要求 PNG Base64 data URL 或 https 图片 URL（见 docs/DEVICE-FACTS.md）。"""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
