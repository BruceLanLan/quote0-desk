"""摇卦页渲染：六爻爻象 + 本卦/变卦名 + 一句判断。

296×152 横屏布局（跟上个项目 200×200 方屏的纵向堆叠不同，这次左右分栏
更利用横向空间）：左栏画六条爻线（自上而下=上爻到初爻），右栏放卦名、
判断语、动爻提示。
"""
from PIL import ImageDraw

from render.base import BLACK, DARK_GRAY, WHITE, font, gray, new_canvas, truncate_to_width, vline

BAR_X0, BAR_X1 = 10, 108
ROW_TOP_Y = [10, 28, 46, 64, 82, 100]  # 行0=上爻 ... 行5=初爻
BAR_THICK = 8
YIN_GAP = 8

TEXT_X0 = 122
DIVIDER_X = 114


def _draw_line(draw: ImageDraw.ImageDraw, row_top: int, is_yang: bool, is_changing: bool):
    y0 = row_top
    y1 = y0 + BAR_THICK
    color = gray(BLACK)
    if is_yang:
        draw.rectangle([BAR_X0, y0, BAR_X1, y1], fill=color)
    else:
        mid = (BAR_X0 + BAR_X1) // 2
        draw.rectangle([BAR_X0, y0, mid - YIN_GAP, y1], fill=color)
        draw.rectangle([mid + YIN_GAP, y0, BAR_X1, y1], fill=color)

    if is_changing:
        cy = (y0 + y1) // 2
        cx = BAR_X1 + 10
        r = 4
        if is_yang:
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=2)
        else:
            draw.line([(cx - r, cy - r), (cx + r, cy + r)], fill=color, width=2)
            draw.line([(cx - r, cy + r), (cx + r, cy - r)], fill=color, width=2)


def render(cast: dict):
    """cast: providers.liuyao.cast_hexagram() 的返回值。"""
    img = new_canvas(bg=WHITE)
    draw = ImageDraw.Draw(img)

    lines = cast["lines"]
    for row, line in enumerate(lines[::-1]):
        _draw_line(draw, ROW_TOP_Y[row], line["is_yang"], line["is_changing"])

    vline(draw, DIVIDER_X, y0=8, y1=144)

    if cast["变卦"]:
        title = f"{cast['本卦']}→{cast['变卦']}"
    else:
        title = f"{cast['本卦']}（不变）"
    f_title = font(16)
    title = truncate_to_width(draw, title, f_title, 296 - TEXT_X0 - 8)
    draw.text((TEXT_X0, 8), title, font=f_title, fill=gray(BLACK))

    judgment = cast.get("判断") or ""
    f_judge = font(12)
    max_w = 296 - TEXT_X0 - 8
    y = 34
    if draw.textlength(judgment, font=f_judge) <= max_w:
        draw.text((TEXT_X0, y), judgment, font=f_judge, fill=gray(DARK_GRAY))
    else:
        mid = len(judgment) // 2
        split_at = judgment.rfind("——", 0, mid + 3)
        split_at = split_at + 2 if split_at != -1 else mid
        line1 = truncate_to_width(draw, judgment[:split_at], f_judge, max_w)
        line2 = truncate_to_width(draw, judgment[split_at:], f_judge, max_w)
        draw.text((TEXT_X0, y), line1, font=f_judge, fill=gray(DARK_GRAY))
        draw.text((TEXT_X0, y + 16), line2, font=f_judge, fill=gray(DARK_GRAY))

    if cast["动爻"]:
        mv_text = "动爻：" + "、".join(str(i) for i in cast["动爻"])
    else:
        mv_text = "六爻不动"
    draw.text((TEXT_X0, 128), mv_text, font=font(12), fill=gray(DARK_GRAY))

    return img
