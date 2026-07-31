"""屏上宠物渲染：ASCII 造型（等宽字体） + 心情/饥饿状态行。

跟六爻/奇门共享 render/base.py 的画布原语，但文字用 `mono_font` 而不是
`font`——ASCII 美术靠字符对齐撑起来，中文字体画拉丁字符宽度不保证一致，
混进去整只宠物会歪掉。
"""
from PIL import ImageDraw

from render.base import BLACK, DARK_GRAY, WHITE, font, gray, hline, mono_font, new_canvas
from render.pet_sprites import EYES, render_frame

ART_FONT_SIZE = 18
ART_LINE_HEIGHT = 21

MOOD_LABEL = {
    "happy": "心满意足",
    "neutral": "还好",
    "hungry": "有点饿了",
    "sad": "很饿了，喂喂它吧",
    "alert": "刚被摸过，精神！",
}


def render(state: dict):
    img = new_canvas(bg=WHITE)
    draw = ImageDraw.Draw(img)

    header = f"{MOOD_LABEL.get(state['mood'], state['mood'])}"
    draw.text((6, 2), header, font=font(14), fill=gray(BLACK))
    hline(draw, 18)

    lines = render_frame(state["species"], state["frame_index"], EYES.get(state["mood"], EYES["neutral"]))
    art_font = mono_font(ART_FONT_SIZE)
    art_width = max(draw.textlength(line, font=art_font) for line in lines)
    x0 = (296 - art_width) / 2
    y0 = 24
    for i, line in enumerate(lines):
        draw.text((x0, y0 + i * ART_LINE_HEIGHT), line, font=art_font, fill=gray(BLACK))

    footer_y = y0 + len(lines) * ART_LINE_HEIGHT + 4
    hline(draw, footer_y)
    footer = f"饥饿 {state['hunger']}% · 上次喂食 {state['last_fed_label']}"
    draw.text((6, footer_y + 4), footer, font=font(12), fill=gray(DARK_GRAY))

    return img
