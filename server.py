"""NFC 回调服务 + 本地控制台。

M2 最小可用：`/t/<action>` 路由，贴一下手机 → 打这个 URL → 服务执行动作 →
`refreshNow` 推新内容回屏幕。第一张验证卡是计数器：贴一下 +1，纯粹验证
"物理动作 -> 服务器 -> 屏幕变化"这条链路通不通，不掺杂业务逻辑。

`link` 目前只能填公网可达的地址（局域网 IP 手机大概率连不上，除非跟设备
同一个 WiFi；M0-P3 会实测到底哪些 scheme 真的能打开）。开发阶段先用
`ngrok`/内网穿透或者手机跟这台机器同一局域网时的私网 IP 测试，正式跑起来
再定长期方案——这个决定记在 docs/DEVICE-FACTS.md 里，不在这里搪塞。

`/` 和 `/settings` 是给人看的本地控制台（参照 pocket-prophet-dashboard
的 app.py 同款结构：`templates/*.html` + `/api/*` JSON 接口），不用记
`cli.py` 的命令行参数也能预览/推送每张卡、开关自动轮换。旧版 `/settings`
直接返回 JSON 的行为搬到了 `/api/config`——这是一个新仓库，没有已知的
外部调用方在依赖旧路径，直接改比留兼容层干净。
"""
import logging

from flask import Flask, jsonify, render_template, request

import config
import dot
import scheduler
from providers.todo import set_task, toggle_done
from push import push_card, render_card
from render import pet_sprites

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("quote0-desk")

app = Flask(__name__)

_counter_state = {"n": 0}

# 控制台"全部内容卡"列表要用的中文名——README 的表格是给人读的 markdown，
# 这里是给前端渲染下拉/按钮用的同一份信息，两处手动保持一致（卡片本身
# 没有一个"人类可读名"的字段，build() 的 alias 是给 Dot App 任务记录看的，
# 不一定适合当 UI 标签）。
CARDS = {
    "proverb": "箴言机",
    "daily": "日课",
    "liuyao": "摇卦",
    "qimen": "奇门遁甲",
    "qiantong": "签筒",
    "status": "Claude Code 状态灯",
    "pet": "屏上宠物",
    "todo": "今日一件事",
    "capsule": "时间胶囊",
    "beacon": "实盘信标",
    "hermes": "Hermes 任务台",
}


def _push_counter():
    d = dot.resolve_device_id()
    n = _counter_state["n"]
    base = config.nfc_base_url()
    link = f"{base}/t/counter_tap" if base else ""
    return dot.push_text(d, title=str(n), message="贴一下 +1", signature="quote0-desk · NFC 计数器",
                          link=link, refresh_now=True, task_alias="NFC 计数器")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/settings")
def settings_page():
    return render_template("settings.html")


@app.route("/api/cards")
def api_cards():
    return jsonify(CARDS)


@app.route("/api/pet_species")
def api_pet_species():
    """可选的宠物造型（只读）。设置页的下拉框用这个接口填选项，前端不硬编码
    一份造型列表——加造型只改 render/pet_sprites.py 一处，UI 自动跟上。

    返回数组而不是对象：Flask 的 jsonify 会按 key 排序，用对象的话下拉框会被
    强制排成字母序，默认的鸭子掉到中间去。数组保得住 SPECIES_LABELS 的顺序。
    """
    return jsonify({
        "options": [{"key": k, "label": v} for k, v in pet_sprites.SPECIES_LABELS.items()],
        "default": pet_sprites.DEFAULT_SPECIES,
    })


@app.route("/api/status")
def api_status():
    """设备在线状态 + 当前屏幕渲染图 URL，控制台首页用来画状态灯和
    "当前显示"预览。永不 500——DotError 大概率是 key 没配好，前端需要
    看见具体原因而不是一个裸的服务器错误页。
    """
    try:
        d = dot.resolve_device_id()
        s = dot.status(d)
        return jsonify({"ok": True, "status": s})
    except dot.DotError as e:
        return jsonify({"ok": False, "hint": str(e)})


@app.route("/api/preview")
def api_preview():
    """只跑 build()，不推送——预览按钮专用。Text API 卡没有本地像素渲染
    （服务端渲染，见 canvas/template.py 的注释），前端拿到 data 字段自己
    排版展示文字，不假装能像素级还原设备上的样子。
    """
    card = request.args.get("card", "")
    if card not in CARDS:
        return jsonify({"ok": False, "hint": f"未知卡片：{card}"}), 404
    try:
        result = render_card(card)
    except Exception as e:
        log.warning("预览 %s 失败: %s", card, e)
        return jsonify({"ok": False, "hint": f"渲染失败：{e}"}), 502
    resp = {"ok": True, "alias": result.get("alias", card)}
    if "png" in result:
        resp["png"] = result["png"]
    if "data" in result:
        resp["data"] = result["data"]
    return jsonify(resp)


@app.route("/api/push", methods=["POST"])
def api_push():
    card = request.args.get("card", "")
    if card not in CARDS:
        return jsonify({"ok": False, "hint": f"未知卡片：{card}"}), 404
    try:
        result = push_card(card)
    except Exception as e:
        log.warning("推送 %s 失败: %s", card, e)
        return jsonify({"ok": False, "hint": f"推送失败：{e}"}), 502
    return jsonify({"ok": True, "push": result})


@app.route("/api/todo", methods=["POST"])
def api_todo():
    """控制台设「今日一件事」用，等价于 cli.py set-todo，但顺手推一次
    到屏幕，不用设完了再手动点一次「推送」。"""
    body = request.get_json(force=True, silent=True) or {}
    task = (body.get("task") or "").strip()
    if not task:
        return jsonify({"ok": False, "hint": "任务不能为空"}), 400
    set_task(task)
    result = push_card("todo")
    return jsonify({"ok": True, "push": result})


@app.route("/api/scheduler_status")
def api_scheduler_status():
    return jsonify(scheduler.get_state())


def _clean_path_list(value) -> list[str]:
    """路径列表：接受数组，也接受设置页 textarea 里一行一个的字符串。空行丢掉；
    整体为空就存空列表，config.path_list_setting() 会退回默认值。"""
    if isinstance(value, str):
        value = value.splitlines()
    if not isinstance(value, list):
        return []
    return [str(p).strip() for p in value if str(p).strip()]


# GET 会原样回吐这些字段（值取 config.load()，即"配置里的原始值"而不是展开
# 后的绝对路径——设置页要把用户填的 `~/...` 原样显示回去）。敏感项不在这里：
# device_id 是设备序列号（更推荐走环境变量），`_auto_push_last_card` 是调度器
# 内部游标，两个都不该给前端编辑。API Key 根本不在 config.json 里。
_EXPOSED_KEYS = [
    "nfc_base_url",
    "auto_push_enabled", "auto_push_interval_minutes", "auto_push_cards",
    "pet_species", "pet_repos",
    "capsule_repos",
    "beacon_lighter_dir", "beacon_stock_radar_dir",
]


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    """控制台设置页的读写口：调度器（布防开关 / 轮换间隔 / 参与轮换的卡列表）、
    NFC 回调地址、宠物造型、各卡要扫的本机路径、箴言缓存参数。
    默认未布防，见 scheduler.py 顶部注释——不要在这里改成默认开启。

    POST 只认 `_EXPOSED_KEYS` 里的字段，其余一律忽略——前端多发了什么字段
    不会被顺手写进 config.json。
    """
    if request.method == "GET":
        cfg = config.load()
        resp = {k: cfg.get(k, config.DEFAULTS.get(k)) for k in _EXPOSED_KEYS}
        resp["scheduler_state"] = scheduler.get_state()
        return jsonify(resp)

    body = request.get_json(force=True, silent=True) or {}
    updates = {}
    if "auto_push_enabled" in body:
        updates["auto_push_enabled"] = bool(body["auto_push_enabled"])
    if "auto_push_interval_minutes" in body:
        updates["auto_push_interval_minutes"] = max(scheduler.MIN_INTERVAL_MINUTES,
                                                      int(body["auto_push_interval_minutes"]))
    if "auto_push_cards" in body:
        updates["auto_push_cards"] = [c for c in body["auto_push_cards"] if c in CARDS]
    if "nfc_base_url" in body:
        updates["nfc_base_url"] = str(body["nfc_base_url"]).strip()
    if "pet_species" in body:
        # 在 API 层就拒绝非法造型。render_frame() 确实有"不认识就画鸭子"的兜底，
        # 但那是渲染时的自保，不该拿来当输入校验——存了个错值再悄悄画成鸭子，
        # 用户只会以为"选了没生效"，排查不到原因。
        species = str(body["pet_species"]).strip()
        if not pet_sprites.is_valid_species(species):
            return jsonify({"ok": False,
                            "hint": f"未知宠物造型：{species}",
                            "options": sorted(pet_sprites.SPECIES)}), 400
        updates["pet_species"] = species
    for key in ("pet_repos", "capsule_repos"):
        if key in body:
            updates[key] = _clean_path_list(body[key])
    for key in ("beacon_lighter_dir", "beacon_stock_radar_dir"):
        if key in body:
            updates[key] = str(body[key]).strip()
    cfg = config.update(**updates)
    return jsonify({"ok": True, "config": cfg})


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
    """摸摸宠物：贴一下触发一次性 heart 状态（对齐官方"被批准"的奖励
    反应），跟 busy/idle/sleep 的判定互不影响，见 providers/pet.py。"""
    from providers.pet import pat
    state = pat()
    result = push_card("pet")
    log.info("pet_pat -> state=%s push=%s", state["state"], result)
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
    scheduler.start()
    app.run(host="0.0.0.0", port=5252, debug=False)
