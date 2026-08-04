"""屏上宠物渲染：ASCII 造型（等宽字体） + 状态标签。

素材和状态命名直接对齐官方 anthropics/claude-desktop-buddy，跟
`render/pet_sprites.py` 共享同一套语义，这个文件只管"怎么画到 296×152
上"——原作用连续动画 + LED 表达 attention 状态的紧迫感，这里退化成
在图案右边加一个静态"!"，静态屏幕能做到的最接近的等价物。
"""
from PIL import ImageDraw

from render.base import BLACK, DARK_GRAY, WHITE, font, gray, hline, mono_font, new_canvas
from render.pet_sprites import render_frame

ART_FONT_SIZE = 18
ART_LINE_HEIGHT = 21

STATE_LABEL = {
    "sleep": "睡着了（没有活动信号）",
    "idle": "空闲",
    "busy": "工作中",
    "attention": "有个操作在等你批准",
    "celebrate": "刚跨过一个 token 里程碑！",
    "heart": "被摸过啦，开心",
}


def render(state: dict):
    img = new_canvas(bg=WHITE)
    draw = ImageDraw.Draw(img)

    header = STATE_LABEL.get(state["state"], state["state"])
    draw.text((6, 2), header, font=font(14), fill=gray(BLACK))
    hline(draw, 18)

    lines = render_frame(state["species"], state["state"], state["frame_index"])
    art_font = mono_font(ART_FONT_SIZE)
    art_width = max(draw.textlength(line, font=art_font) for line in lines)
    x0 = (296 - art_width) / 2
    y0 = 24
    for i, line in enumerate(lines):
        draw.text((x0, y0 + i * ART_LINE_HEIGHT), line, font=art_font, fill=gray(BLACK))
    if state["state"] == "attention":
        draw.text((x0 + art_width + 6, y0), "!", font=art_font, fill=gray(BLACK))

    footer_y = y0 + len(lines) * ART_LINE_HEIGHT + 4
    hline(draw, footer_y)
    footer = f"上次活跃 {state['last_active_label']}"
    draw.text((6, footer_y + 4), footer, font=font(12), fill=gray(DARK_GRAY))

    return img
