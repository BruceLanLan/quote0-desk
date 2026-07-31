"""桌面箴言机卡：当前一句 + 时间戳。NFC 贴一下换下一句（见 server.py
的 /t/proverb_next）。"""
from datetime import datetime

from canvas.template import simple_card, simple_data
from providers.proverb import current


def build() -> dict:
    text = current()
    title = "箴言机"
    footer = datetime.now().strftime("%m-%d %H:%M") + "　贴一下换一句"

    data = simple_data(title=title, message=text, footer=footer)
    window_data = simple_card(title=title, message=text, footer=footer,
                               title_size=16, message_size=20, footer_size=12)
    return {"data": data, "window_data": window_data, "alias": "箴言机", "link": ""}
