"""奇门遁甲九宫格渲染，296×152 横屏。

跟上个项目 200×200 方屏的九宫格不同：横屏格子更扁（宽>高），三行放不下
"方位/门星/干支"三行还要留页眉页脚的空间，所以砍掉方位这一行——
方位信息本来就能从格子在 3×3 里的物理位置推断（艮宫在左下、乾宫在右下等，
这是传统九宫图本身自带的空间语义），保留门/星/干支两行是信息密度和
可读性的折中点。
"""
from PIL import ImageDraw

from render.base import BLACK, DARK_GRAY, WHITE, font, gray, hline, new_canvas, truncate_to_width

GRID_X0, GRID_Y0 = 4, 20
GRID_X1, GRID_Y1 = 292, 138
CELL_W = (GRID_X1 - GRID_X0) / 3
CELL_H = (GRID_Y1 - GRID_Y0) / 3
FOOTER_Y = 140


def _draw_cell(draw: ImageDraw.ImageDraw, cx: float, cy: float, cell: dict, f):
    border = gray(BLACK) if cell.get("is_zhi_fu") else gray(DARK_GRAY)
    draw.rectangle([cx, cy, cx + CELL_W, cy + CELL_H], outline=border, width=2 if cell.get("is_zhi_fu") else 1)

    if cell["is_zhong"]:
        draw.text((cx + 4, cy + 3), "中宫", font=f, fill=gray(BLACK))
        draw.text((cx + 4, cy + 19), cell["star"], font=f, fill=gray(BLACK))
        return

    draw.text((cx + 4, cy + 3), f"{cell['men']} {cell['star'][-1]}", font=f, fill=gray(BLACK))
    gan = cell["di_gan"] if cell["di_gan"] == cell["tian_gan"] else f"{cell['di_gan']}/{cell['tian_gan']}"
    draw.text((cx + 4, cy + 19), gan, font=f, fill=gray(DARK_GRAY))


def render(cast: dict):
    img = new_canvas(bg=WHITE)
    draw = ImageDraw.Draw(img)

    header = f"{cast['dt'].strftime('%H:%M')}  {cast['ju']}"
    draw.text((6, 2), header, font=font(14), fill=gray(BLACK))
    hline(draw, 18)

    f12 = font(12)
    for i, cell in enumerate(cast["cells"]):
        r, c = divmod(i, 3)
        _draw_cell(draw, GRID_X0 + c * CELL_W, GRID_Y0 + r * CELL_H, cell, f12)

    footer = f"值符：{cast['zhi_fu_star']}（{cast['zhi_fu_gong']}宫，粗框标注）"
    footer = truncate_to_width(draw, footer, f12, 284)
    draw.text((6, FOOTER_Y), footer, font=f12, fill=gray(DARK_GRAY))

    return img
