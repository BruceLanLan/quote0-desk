"""Claude Code 状态灯：从纯文字（Text API）换成带进度条的图形卡（Image API）。

原来这张卡是 `canvas.template.simple_data()` 拼三行文字，配额百分比就是
"5h 43% · 7d 12%"这样的数字堆在一起——用户反馈"缺少可视化"，数字本身
不是不能看，但一眼扫过去感受不到"还有多少余量"，视觉上跟别的图形卡
（宠物、摇卦爻线）比显得单薄。

换成横条进度条：配额可用时画两条（5h/7d），不可用时（token 过期/端点
没返回）退回一个更大的数字展示，不画假的进度条——没有真实上限的数字
硬画一条"填了多少"的条，是在编造一个不存在的参照系，比不画更误导人。
"""
from __future__ import annotations

from PIL import ImageDraw

from render.base import BLACK, DARK_GRAY, WHITE, WIDTH, font, gray, hline, new_canvas, truncate_to_width

STATE_ICON = {
    # "◉"（FISHEYE）在 STHeiti Medium 里没有真实字形，会画成一个方框
    # 占位符——实测过（渲染出来是个空心矩形，不是字符本身的问题），
    # 换成"◎"（BULLSEYE），这套字体里有对应字形。
    "attention": "◎",
    "busy": "●",
    "idle": "○",
}
STATE_TEXT = {
    "attention": "等你批准",
    "busy": "工作中",
    "idle": "空闲",
}

BAR_X0 = 46
BAR_X1 = WIDTH - 38  # 右侧留够「100%」三个字符的宽度，填充满格时数字画在条外也不会被裁掉
BAR_H = 14


def _fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _bar(draw: ImageDraw.ImageDraw, y: int, label: str, pct: float):
    draw.text((6, y + 1), label, font=font(12), fill=gray(BLACK))
    draw.rectangle([BAR_X0, y, BAR_X1, y + BAR_H], outline=gray(BLACK), width=1)
    fill_w = int((BAR_X1 - BAR_X0 - 2) * min(max(pct, 0), 100) / 100)
    if fill_w > 0:
        draw.rectangle([BAR_X0 + 1, y + 1, BAR_X0 + 1 + fill_w, y + BAR_H - 1], fill=gray(BLACK))
    pct_text = f"{pct:.0f}%"
    tw = draw.textlength(pct_text, font=font(12))
    filled_edge = BAR_X0 + 1 + fill_w
    # 数字紧跟在填充边缘右侧，跟着条的填充程度走（不是固定画在条的某个
    # 端点）——这样数字的位置本身也是进度的一部分视觉信息，不只是条形。
    # 填充太满、条内空白区域装不下数字时，改画到整条外面的右侧，颜色
    # 固定用黑色：那两种情况数字所在位置背景都是白的，不用再判断填充色。
    if filled_edge + 4 + tw <= BAR_X1:
        draw.text((filled_edge + 4, y + 1), pct_text, font=font(12), fill=gray(BLACK))
    else:
        draw.text((BAR_X1 + 4, y + 1), pct_text, font=font(12), fill=gray(BLACK))


def render(state_name: str, project: str | None, quota: dict, today_tokens: int, cost: float) -> "Image.Image":
    img = new_canvas(bg=WHITE)
    draw = ImageDraw.Draw(img)

    icon = STATE_ICON.get(state_name, "○")
    text = STATE_TEXT.get(state_name, state_name)
    draw.text((6, 4), f"{icon} {text}", font=font(16), fill=gray(BLACK))
    hline(draw, 26)

    if quota.get("available"):
        y = 34
        five_hour = quota.get("five_hour")
        seven_day = quota.get("seven_day")
        if five_hour:
            _bar(draw, y, "5H", five_hour["utilization"])
            y += BAR_H + 12
        if seven_day:
            _bar(draw, y, "7D", seven_day["utilization"])
            y += BAR_H + 12
        footer_y = max(y + 6, 96)
    else:
        label = "今日用量（配额未知）"
        draw.text((6, 36), label, font=font(12), fill=gray(DARK_GRAY))
        big = f"{_fmt_tokens(today_tokens)} tokens"
        bf = font(26)
        bw = draw.textlength(big, font=bf)
        draw.text(((WIDTH - bw) / 2, 56), big, font=bf, fill=gray(BLACK))
        cost_text = f"约 ${cost:.2f}"
        cf = font(14)
        cw = draw.textlength(cost_text, font=cf)
        draw.text(((WIDTH - cw) / 2, 90), cost_text, font=cf, fill=gray(DARK_GRAY))
        footer_y = 114

    hline(draw, footer_y)
    project_line = f"项目：{project}" if project else "最近无活动"
    project_line = truncate_to_width(draw, project_line, font(13), WIDTH - 12)
    draw.text((6, footer_y + 6), project_line, font=font(13), fill=gray(BLACK))

    return img
