"""桌面箴言机卡：当前一句 + 时间戳。NFC 贴一下换下一句（见 server.py
的 /t/proverb_next）。"""
from datetime import datetime

from canvas.template import simple_data
from providers.proverb import current


def build() -> dict:
    text = current()
    title = "箴言机"
    footer = datetime.now().strftime("%m-%d %H:%M") + "　贴一下换一句"

    data = simple_data(title=title, message=text, footer=footer)
    return {"data": data, "alias": "箴言机", "link": ""}
