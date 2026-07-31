#!/usr/bin/env python3
"""M0 真机契约验证：跑不需要用户贴手机的那几项（P1/P4/P5/P6/P7）。

P2/P3（NFC 语义、link scheme）需要用户物理贴手机确认，不在这个脚本里，
见 docs/DEVICE-FACTS.md 里对应章节的手工步骤。

用法：
  export DOT_API_KEY=dot_xxx...
  export DOT_DEVICE_ID=<你的设备序列号>  # 只有一台设备时也可以不填，自动发现
  python3 scripts/m0_probe.py p1   # 或 p4 / p5 / p6 / p7 / all
"""
import sys
import time
from datetime import datetime

sys.path.insert(0, ".")

import dot  # noqa: E402


def device_id():
    return dot.resolve_device_id()


def p1_latency():
    """text refreshNow 延迟：从 POST 返回到 renderInfo.last / current.image 变化。"""
    d = device_id()
    before = dot.status(d)
    before_last = before["renderInfo"]["last"]
    before_img = before["renderInfo"]["current"]["image"]
    print(f"[P1] 推送前 renderInfo.last = {before_last}")

    t0 = time.monotonic()
    r = dot.push_text(d, title="M0-P1", message=f"latency probe {datetime.now().isoformat()}", refresh_now=True)
    t1 = time.monotonic()
    print(f"[P1] POST 返回耗时 {t1 - t0:.2f}s，结果: {r}")
    if not r["ok"]:
        print("[P1] 推送失败，无法测延迟。")
        return

    for i in range(30):
        time.sleep(1)
        s = dot.status(d)
        cur_last = s["renderInfo"]["last"]
        cur_img = s["renderInfo"]["current"]["image"]
        if cur_last != before_last or cur_img != before_img:
            t2 = time.monotonic()
            print(f"[P1] 第 {i+1} 秒检测到变化：renderInfo.last = {cur_last}")
            print(f"[P1] 从 POST 发出到状态变化耗时 ≈ {t2 - t0:.2f}s")
            print(f"[P1] 新 image URL: {cur_img}")
            return
    print("[P1] 30 秒内未检测到 renderInfo 变化——需要人工核对屏幕是否已更新。")


def p4_slot_model():
    """槽模型：不带 taskKey 直接推 canvas，看是创建新槽还是要求已存在的槽。"""
    d = device_id()
    print("[P4] 推送前 loop/list:", dot.list_content(d, "loop"))
    print("[P4] 推送前 fixed/list:", dot.list_content(d, "fixed"))

    window_data = {
        "default": [{
            "type": "div",
            "props": {
                "tw": "flex flex-col w-full h-full bg-white text-black items-center justify-center",
                "children": [{
                    "type": "span",
                    "props": {"tw": "text-24-chillduansans font-bold", "children": "{{get inputData \"msg\" default=\"M0-P4\"}}"},
                }],
            },
        }],
    }
    r = dot.push_canvas(d, data={"msg": "M0-P4 槽模型探测"}, window_data=window_data, refresh_now=True)
    print("[P4] 推送结果:", r)

    print("[P4] 推送后 loop/list:", dot.list_content(d, "loop"))
    print("[P4] 推送后 fixed/list:", dot.list_content(d, "fixed"))


def p5_font_size():
    """中文字号下限：296x152 横屏，从 20 降到 10 逐级推，每档推送后自动下载
    renderInfo.current.image 存到 scripts/_m0_shots/，不需要人工看实物屏——
    调用方（我）事后用 Read 工具直接看这些 PNG 自己判断可读性。"""
    import os
    import requests as _rq

    d = device_id()
    out_dir = os.path.join(os.path.dirname(__file__), "_m0_shots")
    os.makedirs(out_dir, exist_ok=True)

    for size in (20, 18, 16, 14, 12, 10):
        window_data = {
            "default": [{
                "type": "div",
                "props": {
                    "tw": "flex flex-col w-full h-full bg-white text-black p-[8px] justify-center",
                    "children": [{
                        "type": "span",
                        "props": {"tw": f"text-{size}-chillduansans", "children": f"字号{size} 口袋先知与Quote零"},
                    }],
                },
            }],
        }
        r = dot.push_canvas(d, data={}, window_data=window_data, refresh_now=True,
                             task_alias=f"P5 font {size}")
        print(f"[P5] size={size} 推送结果: {r}")
        if not r["ok"]:
            continue
        time.sleep(3)  # 给设备一点时间完成渲染再读 renderInfo
        s = dot.status(d)
        img_urls = s["renderInfo"]["current"]["image"]
        if img_urls:
            png = _rq.get(img_urls[0], timeout=10).content
            path = os.path.join(out_dir, f"p5_size{size}.png")
            with open(path, "wb") as f:
                f.write(png)
            print(f"[P5] 已下载渲染图: {path}")


def p6_grayscale():
    """纯黑白二值还是有灰阶：推一张分 5 段的灰度条 PNG。"""
    from PIL import Image
    import base64
    import io

    img = Image.new("L", (296, 152), 255)
    px = img.load()
    bands = [0, 64, 128, 192, 255]
    band_w = 296 // len(bands)
    for i, v in enumerate(bands):
        for x in range(i * band_w, (i + 1) * band_w):
            for y in range(152):
                px[x, y] = v
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    d = device_id()
    r = dot.push_image(d, image=data_url, dither_type="NONE", dither_kernel="THRESHOLD", refresh_now=True)
    print("[P6] 推送结果:", r)
    if not r["ok"]:
        return
    time.sleep(3)
    s = dot.status(d)
    img_urls = s["renderInfo"]["current"]["image"]
    if img_urls:
        import os
        import requests as _rq
        out_dir = os.path.join(os.path.dirname(__file__), "_m0_shots")
        os.makedirs(out_dir, exist_ok=True)
        png = _rq.get(img_urls[0], timeout=10).content
        path = os.path.join(out_dir, "p6_grayscale.png")
        with open(path, "wb") as f:
            f.write(png)
        print(f"[P6] 已下载渲染图: {path}（自己读图判断是否有中间灰阶）")


def p7_image_url_check():
    """确认 renderInfo.current.image 真的反映最近一次推送内容——自动下载核对，
    不需要人工操作。"""
    import os
    import requests as _rq

    d = device_id()
    s = dot.status(d)
    urls = s["renderInfo"]["current"]["image"]
    print("[P7] 当前 renderInfo.current.image:", urls)
    if urls:
        out_dir = os.path.join(os.path.dirname(__file__), "_m0_shots")
        os.makedirs(out_dir, exist_ok=True)
        png = _rq.get(urls[0], timeout=10).content
        path = os.path.join(out_dir, "p7_current.png")
        with open(path, "wb") as f:
            f.write(png)
        print(f"[P7] 已下载: {path}")


PROBES = {"p1": p1_latency, "p4": p4_slot_model, "p5": p5_font_size,
          "p6": p6_grayscale, "p7": p7_image_url_check}

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    targets = PROBES.keys() if which == "all" else [which]
    for name in targets:
        print(f"\n===== 运行 {name} =====")
        PROBES[name]()
