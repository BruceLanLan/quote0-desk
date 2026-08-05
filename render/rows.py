"""状态板 / 应期复盘这类"多行结构化记录"卡片的像素渲染——走 Image API，
不是 `canvas/template.py` 那种 Text API 数据形状。多行表格这条排版需求
Text API 从没验证过能不能撑住（见 `docs/DEVICE-FACTS.md`），Image API 有
现成的、已验证过的本地 PIL 渲染路径，直接复用 `render/base.py` 的原语，
不需要新的绘图能力，只是把已有的原语组合成"标题 + 两列多行 + footer"
这个新布局。

296×152 画布的预算很紧：标题 + 分隔线用掉约 20px，footer + 分隔线另外
要留约 20px，中间留给正文的大约 112px，18px 一行最多装 5 行——这是脑爆
阶段用真实渲染测出来的，不是纸面算术，`MAX_ROWS` 就定在这条线上，调用方
（`providers/agent_board.py` 等）的存储层行数上限要跟这里保持一致，不能
只在渲染层兜底。

列对齐靠 x 坐标（label 列 x=8，value 列 x=100），不用空格拼——STHeiti
的空格宽度只有 3px，中文字宽 12px，数字宽度又不一样，空格 padding 在
这个字体上必然对不齐，见规划文档里的实测记录。
"""
from __future__ import annotations

from PIL import ImageDraw

from render.base import (
    BLACK,
    DARK_GRAY,
    HEIGHT,
    WHITE,
    WIDTH,
    font,
    gray,
    hline,
    new_canvas,
    to_data_url,
    truncate_to_width,
)

TITLE_FONT_SIZE = 16
ROW_FONT_SIZE = 12
FOOTER_FONT_SIZE = 12
ROW_HEIGHT = 18
LABEL_X = 8
LABEL_WIDTH = 84  # label 列可用宽度，VALUE_X - LABEL_X 再留一点间隔
VALUE_X = 100
VALUE_WIDTH = WIDTH - VALUE_X - 8
MAX_ROWS = 5  # 标题 + 5 行 + footer 是这块画布的排版预算上限，见模块说明


def build_rows_png(title: str, rows: list[tuple[str, str]], footer: str = "") -> str:
    """`title` 顶部标题；`rows` 是 `(label, value)` 列表，超出 `MAX_ROWS` 的
    直接丢弃——调用方的存储层应该已经做过上限截断，这里只是渲染层的最后
    一道防线，不假设调用方一定守规矩。`footer` 可选，底部一行小字（一般
    用来标注来源，比如"quote0-desk · 状态板"）。返回值是
    `to_data_url()` 编码好的 data URL，可以直接喂给 `dot.push_image()`。
    """
    img = new_canvas(bg=WHITE)
    draw = ImageDraw.Draw(img)

    title = truncate_to_width(draw, title, font(TITLE_FONT_SIZE), WIDTH - 12)
    draw.text((6, 2), title, font=font(TITLE_FONT_SIZE), fill=gray(BLACK))
    hline(draw, 22)

    row_font = font(ROW_FONT_SIZE)
    y = 28
    for label, value in rows[:MAX_ROWS]:
        label = truncate_to_width(draw, str(label), row_font, LABEL_WIDTH)
        value = truncate_to_width(draw, str(value), row_font, VALUE_WIDTH)
        draw.text((LABEL_X, y), label, font=row_font, fill=gray(BLACK))
        draw.text((VALUE_X, y), value, font=row_font, fill=gray(BLACK))
        y += ROW_HEIGHT

    if footer:
        footer_y = HEIGHT - 20
        hline(draw, footer_y)
        footer = truncate_to_width(draw, footer, font(FOOTER_FONT_SIZE), WIDTH - 12)
        draw.text((6, footer_y + 4), footer, font=font(FOOTER_FONT_SIZE), fill=gray(DARK_GRAY))

    return to_data_url(img)
