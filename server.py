"""NFC 回调服务 + 预览页。

M2 最小可用：`/t/<action>` 路由，贴一下手机 → 打这个 URL → 服务执行动作 →
`refreshNow` 推新内容回屏幕。第一张验证卡是计数器：贴一下 +1，纯粹验证
"物理动作 -> 服务器 -> 屏幕变化"这条链路通不通，不掺杂业务逻辑。

`link` 目前只能填公网可达的地址（局域网 IP 手机大概率连不上，除非跟设备
同一个 WiFi；M0-P3 会实测到底哪些 scheme 真的能打开）。开发阶段先用
`ngrok`/内网穿透或者手机跟这台机器同一局域网时的私网 IP 测试，正式跑起来
再定长期方案——这个决定记在 docs/DEVICE-FACTS.md 里，不在这里搪塞。
"""
import logging

from flask import Flask, jsonify

import config
import dot
from canvas.template import simple_card, simple_data
from providers.todo import toggle_done
from push import push_card

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("quote0-desk")

app = Flask(__name__)

_counter_state = {"n": 0}


def _push_counter():
    d = dot.resolve_device_id()
    n = _counter_state["n"]
    window_data = simple_card(title=f"{n}", message="贴一下 +1", footer="quote0-desk · NFC 计数器")
    data = simple_data(title=str(n), message="贴一下 +1", footer="quote0-desk · NFC 计数器")
    return dot.push_canvas(d, data=data, window_data=window_data, refresh_now=True, task_alias="NFC 计数器")


@app.route("/")
def index():
    return jsonify({"ok": True, "service": "quote0-desk", "counter": _counter_state["n"]})


@app.route("/t/counter_tap", methods=["GET", "POST"])
def t_counter_tap():
    """M2 最小验证：贴一下数字 +1，立刻推回屏幕。"""
    _counter_state["n"] += 1
    result = _push_counter()
    log.info("counter_tap -> n=%s push=%s", _counter_state["n"], result)
    return jsonify({"n": _counter_state["n"], "push": result})


@app.route("/t/todo_toggle", methods=["GET", "POST"])
def t_todo_toggle():
    """今日一件事打卡：贴一下切换完成状态，立刻推回屏幕。"""
    state = toggle_done()
    result = push_card("todo")
    log.info("todo_toggle -> %s push=%s", state, result)
    return jsonify({"state": state, "push": result})


@app.route("/t/proverb_next", methods=["GET", "POST"])
def t_proverb_next():
    """箴言机换一句：贴一下翻到下一条种子缓存，立刻推回屏幕。"""
    from providers.proverb import advance
    advance()
    result = push_card("proverb")
    log.info("proverb_next push=%s", result)
    return jsonify({"push": result})


@app.route("/t/qiantong", methods=["GET", "POST"])
def t_qiantong():
    """签筒：贴一下真随机抽一签（摇卦或奇门二选一）。"""
    result = push_card("qiantong")
    log.info("qiantong push=%s", result)
    return jsonify({"push": result})


@app.route("/t/pet_pat", methods=["GET", "POST"])
def t_pet_pat():
    """摸摸宠物：贴一下触发一次性精神反应，不影响饥饿值（真正的喂食靠
    commit 触发，见 providers/pet.py）。"""
    from providers.pet import pat
    state = pat()
    result = push_card("pet")
    log.info("pet_pat -> mood=%s push=%s", state["mood"], result)
    return jsonify({"state": state, "push": result})


@app.route("/t/ping")
def t_ping():
    """M0-P2/P3 探测用：贴一下只记录一次命中，不推送，用来先确认 NFC
    到底能不能打开这个 URL（跟"打开后还要不要推送"分开验证，避免一次测
    两件事、出问题分不清是哪一半坏的）。
    """
    log.info("ping hit")
    return jsonify({"ok": True, "message": "NFC/浏览器成功打开了这个 URL"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5252, debug=False)
