"""今日一件事卡：显示今天的承诺 + 完成状态，NFC 贴一下打卡（见 server.py
的 /t/todo_toggle）。"""
from canvas.template import simple_data
from config import nfc_base_url
from providers.todo import get_today


def build() -> dict:
    t = get_today()
    if not t["task"]:
        title = "今日一件事"
        message = "还没定今天要做的事\n（python3 cli.py set-todo \"...\"）"
        footer = ""
    else:
        title = "✓ 已完成" if t["done"] else "今日一件事"
        message = t["task"]
        footer = t["date"] + ("　贴一下可撤销" if t["done"] else "　完成后贴一下打卡")

    base = nfc_base_url()
    link = f"{base}/t/todo_toggle" if base else ""
    data = simple_data(title=title, message=message, footer=footer)
    return {"data": data, "alias": "今日一件事", "link": link}
