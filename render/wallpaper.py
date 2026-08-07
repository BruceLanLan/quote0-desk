"""默认壁纸：用户还没上传自己的图时，屏幕显示这张。

用的是真实的云南甲马版画「招财进宝」（`render/assets/zhaocai_jinbao.jpg`），
不是本地画的图形——早期版本试过纯 PIL 画的"八方来财"四个字+简化图形，
用户反馈"太简单了，建议找更中式的图"，换成了这张传统木刻版画：

**来源与授权**：Wikimedia Commons，
<https://commons.wikimedia.org/wiki/File:%E4%BA%91%E5%8D%97%E7%94%B2%E9%A9%AC-%E6%8B%9B%E8%B4%A2%E8%BF%9B%E5%AE%9D.jpg>，
摄影者 Pygathrix，CC BY-SA 4.0（署名-相同方式共享）。这里存的
`render/assets/zhaocai_jinbao.jpg` 是从原图裁掉外框和木板背景后的版本，
仍然是这份授权下的演绎作品，同样以 CC BY-SA 4.0 提供——这条许可跟
`quote0-desk` 仓库本身的 MIT 协议是两回事，只覆盖这一个文件，不影响
仓库其它代码。

**为什么选木刻版画而不是彩色照片**：296×152 纯黑白屏，任何图片最终都要
过一遍 `Image.FLOYDSTEINBERG` 抖动——木刻版画本身就是粗黑线条+大片留白，
抖动之后基本不失真；彩色照片的连续色调抖动后大概率糊成一片噪点，试过
一版效果明显更差。

**排版**：原版画是竖构图（标题横排在上，两位财神站在下面），跟设备
296×152 的横屏比例差得远，直接铺满裁切会切掉标题或人物。改成"整幅
缩放到画面中央，两侧留白画装饰性铜钱"——保留完整构图（标题+人物都在），
两侧留白也没浪费，比横向裁切损失内容、或者拉伸变形都更合适这块小屏幕。
"""
import os

from PIL import Image, ImageDraw

from render.base import BLACK, HEIGHT, WIDTH, gray, new_canvas

ASSET_PATH = os.path.join(os.path.dirname(__file__), "assets", "zhaocai_jinbao.jpg")

ART_MAX_WIDTH = 200
ART_MAX_HEIGHT = HEIGHT - 10
COIN_RADIUS = 10


def _coin(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int):
    """铜钱：外圆 + 中间方孔，画在版画两侧的留白区域，不让留白显得是
    没排好版，而是"这本来就是设计的一部分"。"""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=gray(BLACK), width=2)
    h = max(2, r // 3)
    draw.rectangle([cx - h, cy - h, cx + h, cy + h], outline=gray(BLACK), width=2)


def default_wallpaper() -> Image.Image:
    canvas = new_canvas(bg=255)
    art = Image.open(ASSET_PATH).convert("RGB")
    art.thumbnail((ART_MAX_WIDTH, ART_MAX_HEIGHT), Image.LANCZOS)

    x = (WIDTH - art.width) // 2
    y = (HEIGHT - art.height) // 2
    canvas.paste(art, (x, y))

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([2, 2, WIDTH - 3, HEIGHT - 3], outline=gray(BLACK), width=2)
    draw.rectangle([6, 6, WIDTH - 7, HEIGHT - 7], outline=gray(BLACK), width=1)

    margin = x
    if margin > 2 * COIN_RADIUS + 6:  # 留白够宽才画铜钱，避免窄屏配置下挤在一起
        for cx in (margin // 2, WIDTH - margin // 2):
            _coin(draw, cx, HEIGHT // 2 - 20, COIN_RADIUS)
            _coin(draw, cx, HEIGHT // 2 + 20, COIN_RADIUS)

    return canvas
