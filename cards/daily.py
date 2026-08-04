"""日课卡：当前时刻的四柱干支（年月日时），Text API 卡。"""
from canvas.template import simple_data
from providers.daily import cast


def build() -> dict:
    c = cast()
    title = f"{c['day_pillar']}日 · {c['hour_pillar']}时"
    message = (
        f"{c['year_pillar']}年 {c['month_pillar']}月 "
        f"{c['day_pillar']}日 {c['hour_pillar']}时\n"
        f"日干五行：{c['day_wuxing']}"
    )
    footer = c["dt"].strftime("%m-%d %H:%M") + "　日课"

    data = simple_data(title=title, message=message, footer=footer)
    return {"data": data, "alias": "日课", "link": ""}
