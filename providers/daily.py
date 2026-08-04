"""日课：当前时刻的四柱干支（年月日时）。跟奇门遁甲共用同一个排盘引擎
（qimen_engine.py 的 datetime_to_question_pillars），但这张卡不起盘、
不算用神九宫格，只看"现在是什么干支"这一件事，所以是比 providers/qimen.py
更轻的一条路径，不重复实现干支计算。
"""
from __future__ import annotations

import datetime

from providers import qimen_engine as qe

WUXING = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
}


def cast(dt: datetime.datetime = None) -> dict:
    """起一次日课。dt 为空则用当前时间。"""
    dt = dt or datetime.datetime.now()
    pillars_str, _ = qe.datetime_to_question_pillars(dt)
    year_p, month_p, day_p, hour_p = pillars_str.split(" ")
    return {
        "dt": dt,
        "year_pillar": year_p,
        "month_pillar": month_p,
        "day_pillar": day_p,
        "hour_pillar": hour_p,
        "day_wuxing": WUXING[day_p[0]],
    }
