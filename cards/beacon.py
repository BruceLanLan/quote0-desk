"""实盘信标卡：lighter-scalper 持仓状态 + stock-radar 最新信号，只读展示。"""
from datetime import datetime, timezone

from canvas.template import simple_data
from providers.beacon import fetch


def _fmt_ago(iso_ts: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_ts)
    except ValueError:
        return iso_ts
    days = (datetime.now(timezone.utc) - dt).days
    if days <= 0:
        return "今天"
    if days == 1:
        return "昨天"
    return f"{days}天前"


def build() -> dict:
    d = fetch()
    lighter = d["lighter"]
    sr = d["stock_radar"]

    if lighter["positions"]:
        lighter_line = "持仓 " + "、".join(lighter["positions"])
    elif lighter["running"]:
        lighter_line = "运行中 · 当前无持仓"
    else:
        lighter_line = "策略未运行"

    if sr:
        sr_line = f"{sr['symbol']} {sr['pattern']} @ {sr['price']}（{_fmt_ago(sr['ts'])}）"
    else:
        sr_line = "暂无信号"

    title = "实盘信标"
    message = f"lighter-scalper：{lighter_line}\nstock-radar：{sr_line}"
    footer = datetime.now().strftime("%m-%d %H:%M 更新")

    data = simple_data(title=title, message=message, footer=footer)
    return {"data": data, "alias": "实盘信标", "link": ""}
