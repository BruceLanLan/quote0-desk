"""把已有的真机截图(docs/img/*.png,296×152 原始尺寸)和本地渲染的宠物
状态,加工成 README 用的展示图:NEAREST 3 倍放大保持像素锐利 + 画一个
简单的冰箱贴边框,让"这是一块真实的墨水屏"这件事看得出来,而不是一张
被浏览器拉伸拉糊的小图。

不新造任何画面内容——放大对象要么是已经真机验证过的截图,要么是
render/pet.py 本来就会生成的、会被真正推上设备的同一份图像。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw

from render.pet import render as render_pet

IMG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "img")

SCALE = 3
BEZEL = 18
CORNER_RADIUS = 10
BEZEL_COLOR = (28, 28, 30)
BG_COLOR = (18, 18, 20)


def bezel_frame(img: Image.Image, scale: int = SCALE) -> Image.Image:
    """真实截图/渲染图 → 像素级放大 + 冰箱贴边框。"""
    up = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    frame_w = up.width + BEZEL * 2
    frame_h = up.height + BEZEL * 2
    frame = Image.new("RGB", (frame_w, frame_h), BG_COLOR)
    mask = Image.new("L", (frame_w, frame_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, frame_w - 1, frame_h - 1], radius=CORNER_RADIUS * scale // 2, fill=255
    )
    bezel_layer = Image.new("RGB", (frame_w, frame_h), BEZEL_COLOR)
    frame = Image.composite(bezel_layer, frame, mask)
    frame.paste(up, (BEZEL, BEZEL))
    return frame


def side_by_side(left: Image.Image, right: Image.Image, gap: int = 28) -> Image.Image:
    h = max(left.height, right.height)
    canvas = Image.new("RGB", (left.width + gap + right.width, h), (255, 255, 255))
    canvas.paste(left, (0, (h - left.height) // 2))
    canvas.paste(right, (left.width + gap, (h - right.height) // 2))
    return canvas


def upgrade_existing():
    for name in ("pet", "liuyao", "qimen", "proverb"):
        src = os.path.join(IMG_DIR, f"{name}.png")
        if not os.path.exists(src):
            print(f"skip {name}: 原图不存在")
            continue
        img = Image.open(src).convert("RGB")
        out = bezel_frame(img)
        out.save(os.path.join(IMG_DIR, f"{name}_hero.png"))
        print(f"{name}_hero.png {out.size}")


def make_pet_state_grid():
    states = ["sleep", "idle", "busy", "attention", "celebrate", "heart"]
    labels_row1, labels_row2 = [], []
    cells = []
    for s in states:
        state = {"species": "duck", "state": s, "frame_index": 0, "last_active_label": "08-04 12:00"}
        img = render_pet(state)
        cells.append(bezel_frame(img, scale=2))
    cell_w, cell_h = cells[0].size
    cols, rows = 3, 2
    gap = 16
    grid = Image.new("RGB", (cell_w * cols + gap * (cols - 1), cell_h * rows + gap * (rows - 1)), (255, 255, 255))
    for i, cell in enumerate(cells):
        x = (i % cols) * (cell_w + gap)
        y = (i // cols) * (cell_h + gap)
        grid.paste(cell, (x, y))
    grid.save(os.path.join(IMG_DIR, "pet_states.png"))
    print(f"pet_states.png {grid.size}")


def make_pet_pat_before_after():
    before_state = {"species": "duck", "state": "idle", "frame_index": 0, "last_active_label": "08-04 11:58"}
    after_state = {"species": "duck", "state": "heart", "frame_index": 0, "last_active_label": "08-04 12:00"}
    before = bezel_frame(render_pet(before_state))
    after = bezel_frame(render_pet(after_state))
    combined = side_by_side(before, after)
    combined.save(os.path.join(IMG_DIR, "pet_pat_before_after.png"))
    print(f"pet_pat_before_after.png {combined.size}")


if __name__ == "__main__":
    os.makedirs(IMG_DIR, exist_ok=True)
    upgrade_existing()
    make_pet_state_grid()
    make_pet_pat_before_after()
