"""默认壁纸：用户还没上传自己的图时，屏幕显示这张。

用的是两张真实的云南甲马版画拼在一起——「招财进宝」+「财神」（虎身
财神持剑），不是本地画的图形。演变过两版：

1. 第一版纯 PIL 画"八方来财"四个字+简化图形。用户反馈"太简单了，
   建议找更中式的图"，换成单张「招财进宝」版画。
2. 单张版画是竖构图（3:4 左右），跟设备 296×152 的横屏（约 1.95:1）
   比例差得远，居中缩放后两侧留白很宽，用户又反馈"这个图可以，但是
   没有这个尺寸和比例的吗"。找了同一位摄影者、同一批云南甲马藏品里
   主题相关的第二张「财神」，两张等高拼接成一张更接近横屏比例的组合图
   （拼接后约 1.53:1，比单张 0.76:1 好得多），两张主题一致（都是财神/
   招财），画风一致（同一批藏品、同一种拍摄方式），拼在一起不违和。

**来源与授权**（两张图都是 Wikimedia Commons，摄影者 Pygathrix，
CC BY-SA 4.0，署名-相同方式共享）：

- 「招财进宝」：`render/assets/zhaocai_jinbao.jpg`，
  <https://commons.wikimedia.org/wiki/File:%E4%BA%91%E5%8D%97%E7%94%B2%E9%A9%AC-%E6%8B%9B%E8%B4%A2%E8%BF%9B%E5%AE%9D.jpg>
- 「财神」：`render/assets/caishen.jpg`，
  <https://commons.wikimedia.org/wiki/File:%E4%BA%91%E5%8D%97%E7%94%B2%E9%A9%AC-%E8%B4%A2%E7%A5%9E.jpg>

这里存的两个文件都是从原图裁掉外框和木板背景后的版本，仍然是这份
授权下的演绎作品，同样以 CC BY-SA 4.0 提供——这条许可只覆盖这两个
素材文件，不影响仓库其它代码的 MIT 协议。

**为什么选木刻版画而不是彩色照片**：296×152 纯黑白屏，任何图片最终都要
过一遍 `Image.FLOYDSTEINBERG` 抖动——木刻版画本身就是粗黑线条+大片留白，
抖动之后基本不失真；彩色照片的连续色调抖动后大概率糊成一片噪点。
"""
import os

from PIL import Image, ImageDraw

from render.base import BLACK, HEIGHT, WIDTH, gray, new_canvas

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
LEFT_PATH = os.path.join(ASSETS_DIR, "zhaocai_jinbao.jpg")
RIGHT_PATH = os.path.join(ASSETS_DIR, "caishen.jpg")


def _combined_art() -> Image.Image:
    """两张图等高拼接——不是简单左右塞进画布，等高缩放能让接缝处两张画
    的顶边/底边对齐，看起来像一组而不是两张随便拼的图。"""
    left = Image.open(LEFT_PATH).convert("RGB")
    right = Image.open(RIGHT_PATH).convert("RGB")
    h = min(left.height, right.height)
    left = left.resize((int(left.width * h / left.height), h), Image.LANCZOS)
    right = right.resize((int(right.width * h / right.height), h), Image.LANCZOS)
    combined = Image.new("RGB", (left.width + right.width, h), (255, 255, 255))
    combined.paste(left, (0, 0))
    combined.paste(right, (left.width, 0))
    return combined


def default_wallpaper() -> Image.Image:
    canvas = new_canvas(bg=255)
    art = _combined_art()
    art.thumbnail((WIDTH - 8, HEIGHT - 8), Image.LANCZOS)

    x = (WIDTH - art.width) // 2
    y = (HEIGHT - art.height) // 2
    canvas.paste(art, (x, y))

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([1, 1, WIDTH - 2, HEIGHT - 2], outline=gray(BLACK), width=2)

    return canvas
