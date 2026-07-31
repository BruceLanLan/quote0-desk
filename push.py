"""共享的"按卡名推送"逻辑，cli.py 和 server.py 都用这一份，不各写一遍。"""
import importlib

import dot


def push_card(card_name: str) -> dict:
    mod = importlib.import_module(f"cards.{card_name}")
    d = dot.resolve_device_id()
    result = mod.build()
    if "png" in result:
        return dot.push_image(d, image=result["png"], link=result.get("link"), refresh_now=True,
                               task_alias=result.get("alias", card_name))
    return dot.push_canvas(d, data=result["data"], window_data=result["window_data"],
                            link=result.get("link"), refresh_now=True,
                            task_alias=result.get("alias", card_name))
