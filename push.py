"""共享的"按卡名推送"逻辑，cli.py 和 server.py 都用这一份，不各写一遍。

设备 loop 槽位只有 2 个能被我们用（Text API + Image API，第 3 个槽被用户
的官方新闻内容占了，Canvas API 槽已经要不回来，见 docs/DEVICE-FACTS.md）。
所以这里只分两路：卡返回 png 就走 Image API，否则走 Text API——不再有
Canvas 分支。
"""
import importlib

import dot


def render_card(card_name: str) -> dict:
    """跟 push_card 一样跑卡片的 build()，但不推送——控制台的"预览"按钮
    用这个，看内容不消耗一次真实的设备推送/API 调用。"""
    mod = importlib.import_module(f"cards.{card_name}")
    return mod.build()


def push_card(card_name: str) -> dict:
    result = render_card(card_name)
    d = dot.resolve_device_id()
    if "png" in result:
        return dot.push_image(d, image=result["png"], link=result.get("link"), refresh_now=True,
                               task_alias=result.get("alias", card_name))
    data = result["data"]
    return dot.push_text(d, title=data.get("title"), message=data.get("message"),
                          signature=data.get("footer"), link=result.get("link"), refresh_now=True,
                          task_alias=result.get("alias", card_name))
