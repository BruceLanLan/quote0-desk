"""共享的"按卡名推送"逻辑，cli.py 和 server.py 都用这一份，不各写一遍。

设备 loop 槽位只有 2 个能被我们用（Text API + Image API，第 3 个槽被用户
的官方新闻内容占了，Canvas API 槽已经要不回来，见 docs/DEVICE-FACTS.md）。
所以这里只分两路：卡返回 png 就走 Image API，否则走 Text API——不再有
Canvas 分支。
"""
import importlib

import dot


def push_card(card_name: str) -> dict:
    mod = importlib.import_module(f"cards.{card_name}")
    d = dot.resolve_device_id()
    result = mod.build()
    if "png" in result:
        return dot.push_image(d, image=result["png"], link=result.get("link"), refresh_now=True,
                               task_alias=result.get("alias", card_name))
    data = result["data"]
    return dot.push_text(d, title=data.get("title"), message=data.get("message"),
                          signature=data.get("footer"), link=result.get("link"), refresh_now=True,
                          task_alias=result.get("alias", card_name))
