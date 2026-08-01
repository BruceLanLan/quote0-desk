"""时间胶囊卡：Canvas 渲染，`link` 可选跳到对应仓库的 GitHub 页面（若仓库
配了 remote，M2 打通后再接；本地 git log 本身没有 commit hash 的公开 URL
就不强行拼一个）。
"""
from canvas.template import simple_data
from providers.capsule import fetch


def build() -> dict:
    c = fetch()
    if c["label"]:
        title = f"{c['label']}的今天"
        message = c["message"]
        footer = f"{c['date']} · {c['repo']}"
    else:
        title = "时间胶囊"
        message = c["message"]
        footer = ""

    data = simple_data(title=title, message=message, footer=footer)
    return {"data": data, "alias": "时间胶囊", "link": ""}
