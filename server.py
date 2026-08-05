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
import sys

from flask import Flask, jsonify, render_template, request

import config
import dot
import scheduler
from providers import agent_board, hermes_inbox, oracle, pomodoro
from providers.todo import set_task, toggle_done
from push import push_card, render_card
from render import pet_sprites
from render.base import to_data_url
from render.divination import render as divination_render

# 显式指到 stdout——launchd 把 stdout/stderr 分别定向到 out.log/err.log
# （见 scripts/launchd/template.plist），logging.basicConfig 不传 stream
# 时默认走 stderr，导致每 5/15 秒一次的 /api/status、/api/scheduler_status
# 轮询记录也全塞进了 err.log，"err.log" 名不副实——真正的报错反而被淹没
# 在海量正常访问记录里，排障时不好找。改到 stdout 之后，err.log 里就只剩
# Python 未捕获异常自己的 traceback（Flask/Werkzeug 直接写 stderr，不受
# 这里的配置影响），符合这个文件名字面的意思。
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                     stream=sys.stdout)
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
    "hermes_inbox": "Hermes 消息",
    "pomodoro": "番茄钟",
    "agent_board": "状态板",
    "oracle_review": "应期复盘",
}


def _push_counter():
    d = dot.resolve_device_id()
    n = _counter_state["n"]
    base = config.nfc_base_url()
    link = f"{base}/t/counter_tap" if base else ""
    return dot.push_text(d, title=str(n), message="贴一下 +1", signature="quote0-desk · NFC 计数器",
                          link=link, refresh_now=True, task_alias="NFC 计数器")


def _safe(fn, *args, **kwargs) -> dict:
    """/t/* 路由统一用这个包一层可能抛异常的推送调用——网络抖动/Dot API 报错
    时返回 {"ok": False, "hint": ...}，路由层直接 jsonify，不会让 NFC 贴一下
    在手机上看到裸的 Flask 500 错误页。这条容错纪律 /api/push、/api/preview
    从一开始就有，/t/* 这批路由是更早的 M2 阶段加的，一直没有补齐——直到一次
    真实的网络代理抖动把 pet_pat 打出 500 才发现覆盖面有多大（真机测试的
    发现，不是凭空推测的场景）。
    """
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        log.warning("NFC 触发的推送失败: %s", e)
        return {"ok": False, "hint": str(e)}


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
    result = _safe(push_card, "todo")
    return jsonify({"ok": True, "push": result})


@app.route("/api/hermes_inbox", methods=["POST"])
def api_hermes_inbox():
    """hermes-quote0 插件（`hermes-quote0/` 子目录）的 send() 落点——Hermes
    agent 主动推一条消息过来，存下并立刻推到屏幕。跟其它 /api/* 端点同一个
    信任模型：只在本机/局域网内可达，不额外加鉴权（这个项目从第一天起就没有
    对公网暴露的设计，见 README「排障」一节）。

    D1 安全设计决策：不接受任何 link 字段——屏幕上这张卡的 link 由
    cards/hermes_inbox.py 固定生成（本轮固定为空），body 里传了也会被忽略，
    这是硬约束，不是文档提醒：agent 会被 prompt injection，不能让它有机会
    通过"自己写一个 link"把物理贴一下变成钓鱼入口。
    """
    body = request.get_json(force=True, silent=True) or {}
    message = str(body.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "hint": "message 不能为空"}), 400
    hermes_inbox.receive(message)
    result = _safe(push_card, "hermes_inbox")
    log.info("hermes_inbox 收到消息并推送: %s", result)
    return jsonify({"ok": True, "push": result})


@app.route("/api/board", methods=["GET"])
def api_board_get():
    """只读查看状态板当前内容——不推送，控制台/调试用。"""
    return jsonify(agent_board.board() or {"rows": []})


@app.route("/api/board/row", methods=["POST"])
def api_board_row():
    """状态板写一行（对话式记录的落点，见 mcp_server 的 board_note 工具）。
    D7 安全设计决策：跟 /api/hermes_inbox 同一个信任模型——只在本机/局域网
    可达、不额外加鉴权；**不接受任何 link 字段**（D1 的延续，MCP 那头同样
    可能被 prompt injection，不能让它有路径把物理贴一下变成钓鱼）。
    """
    body = request.get_json(force=True, silent=True) or {}
    label = str(body.get("label") or "").strip()
    value = str(body.get("value") or "").strip()
    if not label:
        return jsonify({"ok": False, "hint": "label 不能为空"}), 400
    agent_board.set_row(label, value)
    result = _safe(push_card, "agent_board")
    log.info("board_row %s=%s push=%s", label, value, result)
    return jsonify({"ok": True, "push": result})


@app.route("/api/board/clear", methods=["POST"])
def api_board_clear():
    """状态板清空 + 立刻推屏，反映"现在没有任何记录"这个状态。"""
    agent_board.clear()
    result = _safe(push_card, "agent_board")
    log.info("board_clear push=%s", result)
    return jsonify({"ok": True, "push": result})


@app.route("/api/oracle/cast", methods=["POST"])
def api_oracle_cast():
    """应期复盘的起卦入口（MCP `cast_with_question` 的落点）：记下问题、
    起一卦、把**这一次**摇到的卦象（不是重新摇一次）立刻推到屏幕。D7
    同一个信任模型：不接受 link 字段，本机/局域网可达即可，不额外加鉴权。

    不走 `push_card("liuyao")`——那张卡的 `build()` 语义是"现摇一卦"，
    会重新调一次 `cast_hexagram()`，随机结果就跟 `oracle.cast()` 已经
    记进日志的卦象对不上了。这里直接调渲染 + 推送，跟 `_push_counter()`
    一样是绕开 `cards/` 抽象层的特例，因为需要渲染和存储共用同一份
    随机结果。
    """
    body = request.get_json(force=True, silent=True) or {}
    question = str(body.get("question") or "").strip()
    entry, full_cast = oracle.cast(question)
    try:
        img = divination_render(full_cast)
        d = dot.resolve_device_id()
        result = dot.push_image(d, image=to_data_url(img), link="", refresh_now=True,
                                 task_alias="带问题的卦")
    except Exception as e:
        log.warning("oracle_cast 推送失败: %s", e)
        result = {"ok": False, "hint": str(e)}
    log.info("oracle_cast question=%s hexagram=%s push=%s", question, entry["hexagram"], result)
    return jsonify({"ok": True, "entry": entry, "push": result})


@app.route("/api/oracle/verdict", methods=["POST"])
def api_oracle_verdict():
    """回答"应了吗"（MCP `oracle_verdict` 的落点），立刻推一次应期复盘卡
    反映最新的命中率。"""
    body = request.get_json(force=True, silent=True) or {}
    answer = str(body.get("answer") or "").strip().lower()
    if answer not in ("yes", "no"):
        return jsonify({"ok": False, "hint": "answer 必须是 yes 或 no"}), 400
    entry = oracle.verdict(answer)
    if entry is None:
        return jsonify({"ok": False, "hint": "目前没有待回答的应期记录"}), 400
    result = _safe(push_card, "oracle_review")
    log.info("oracle_verdict answer=%s push=%s", answer, result)
    return jsonify({"ok": True, "entry": entry, "push": result})


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
    "pomodoro_minutes",
    "oracle_review_days",
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
        try:
            interval = int(body["auto_push_interval_minutes"])
        except (TypeError, ValueError):
            return jsonify({"ok": False, "hint": "auto_push_interval_minutes 必须是数字"}), 400
        updates["auto_push_interval_minutes"] = max(scheduler.MIN_INTERVAL_MINUTES, interval)
    if "auto_push_cards" in body:
        raw_cards = body["auto_push_cards"]
        if not isinstance(raw_cards, list):
            return jsonify({"ok": False, "hint": "auto_push_cards 必须是数组"}), 400
        updates["auto_push_cards"] = [c for c in raw_cards if c in CARDS]
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
            raw = body[key]
            # _clean_path_list() 对不认识的类型故意"宽容"地退回空列表——那个
            # 宽容是为了不让奇怪输入崩掉，但在这里（设置页保存）会变成静默
            # 清空用户配置：传个数字/对象进来，返回 200，pet_repos 却被清空
            # 了，用户毫无察觉。类型检查提前到这里做，非法类型直接拒绝，
            # 空字符串/空数组这两种"合法的清空信号"仍然放行。
            if not isinstance(raw, (str, list)):
                return jsonify({"ok": False, "hint": f"{key} 必须是数组或字符串"}), 400
            updates[key] = _clean_path_list(raw)
    for key in ("beacon_lighter_dir", "beacon_stock_radar_dir"):
        if key in body:
            updates[key] = str(body[key]).strip()
    if "pomodoro_minutes" in body:
        try:
            minutes = int(body["pomodoro_minutes"])
        except (TypeError, ValueError):
            return jsonify({"ok": False, "hint": "pomodoro_minutes 必须是数字"}), 400
        updates["pomodoro_minutes"] = max(1, minutes)
    if "oracle_review_days" in body:
        try:
            days = int(body["oracle_review_days"])
        except (TypeError, ValueError):
            return jsonify({"ok": False, "hint": "oracle_review_days 必须是数字"}), 400
        updates["oracle_review_days"] = max(1, days)
    cfg = config.update(**updates)
    return jsonify({"ok": True, "config": cfg})


@app.route("/t/counter_tap", methods=["GET", "POST"])
def t_counter_tap():
    """M2 最小验证：贴一下数字 +1，立刻推回屏幕。"""
    _counter_state["n"] += 1
    result = _safe(_push_counter)
    log.info("counter_tap -> n=%s push=%s", _counter_state["n"], result)
    return jsonify({"n": _counter_state["n"], "push": result})


@app.route("/t/todo_toggle", methods=["GET", "POST"])
def t_todo_toggle():
    """今日一件事打卡：贴一下切换完成状态，立刻推回屏幕。"""
    state = toggle_done()
    result = _safe(push_card, "todo")
    log.info("todo_toggle -> %s push=%s", state, result)
    return jsonify({"state": state, "push": result})


@app.route("/t/proverb_next", methods=["GET", "POST"])
def t_proverb_next():
    """箴言机换一句：贴一下翻到下一条种子缓存，立刻推回屏幕。"""
    from providers.proverb import advance
    advance()
    result = _safe(push_card, "proverb")
    log.info("proverb_next push=%s", result)
    return jsonify({"push": result})


@app.route("/t/qiantong", methods=["GET", "POST"])
def t_qiantong():
    """签筒：贴一下真随机抽一签（摇卦或奇门二选一）。"""
    result = _safe(push_card, "qiantong")
    log.info("qiantong push=%s", result)
    return jsonify({"push": result})


@app.route("/t/pet_pat", methods=["GET", "POST"])
def t_pet_pat():
    """摸摸宠物：贴一下触发一次性 heart 状态（对齐官方"被批准"的奖励
    反应），跟 busy/idle/sleep 的判定互不影响，见 providers/pet.py。"""
    from providers.pet import pat
    state = pat()
    result = _safe(push_card, "pet")
    log.info("pet_pat -> state=%s push=%s", state["state"], result)
    return jsonify({"state": state, "push": result})


@app.route("/t/pomodoro", methods=["GET", "POST"])
def t_pomodoro():
    """番茄钟：贴一下开始一个专注块（空闲时），或提前结束（进行中时），
    立刻推回屏幕。到点后的"结束了"通知走 scheduler 的 urgent 队列，不经
    过这个路由（见 providers/pomodoro.py 的 watcher）。"""
    state = pomodoro.toggle()
    result = _safe(push_card, "pomodoro")
    log.info("pomodoro -> %s push=%s", state, result)
    return jsonify({"state": state, "push": result})


@app.route("/t/oracle_verdict", methods=["GET", "POST"])
def t_oracle_verdict():
    """应期复盘：贴一下记为"应验了"。Quote/0 一张卡只有一个 link，没法
    像手机 App 那样弹"是/否"两个按钮，所以贴一下固定对应更有仪式感的
    "应验了"（yes）——"没应验"这个结果预期主要靠对话跟 Claude 说
    （MCP 的 oracle_verdict("no")），这是简化，如实记在这里。
    """
    entry = oracle.verdict("yes")
    result = _safe(push_card, "oracle_review")
    log.info("oracle_verdict(yes) -> %s push=%s", entry, result)
    return jsonify({"entry": entry, "push": result})


@app.route("/t/ping")
def t_ping():
    """M0-P2/P3 探测用：贴一下只记录一次命中，不推送，用来先确认 NFC
    到底能不能打开这个 URL（跟"打开后还要不要推送"分开验证，避免一次测
    两件事、出问题分不清是哪一半坏的）。
    """
    log.info("ping hit")
    return jsonify({"ok": True, "message": "NFC/浏览器成功打开了这个 URL"})


@app.route("/t/probe_form", methods=["GET", "POST"])
def t_probe_form():
    """一次性探针：NFC 目前六个 /t/* 路由全是零参数的（贴一下=执行一个固定
    动作），从没验证过"贴一下能不能打开一个可输入的网页并成功提交"。这条
    结论决定后续"带问题的卦""NFC 改宠物名"这类功能能不能做，所以先用一个
    极简表单探一次——纯 HTML，无 JS、无外部资源，尽量兼容 Dot App 内置浏览器
    这种可能功能残缺的 WebView。

    验证完这条如果证实可行，`docs/DEVICE-FACTS.md` 记一笔就行，这个路由
    本身是一次性的，不需要长期保留成正式功能。
    """
    if request.method == "GET":
        html = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:sans-serif;padding:24px;font-size:18px">
<form method="POST">
<label>随便写点什么：</label><br>
<input type="text" name="value" style="font-size:18px;padding:8px;width:80%"><br><br>
<button type="submit" style="font-size:18px;padding:10px 24px">提交</button>
</form></body></html>"""
        return html
    value = request.form.get("value", "")
    log.info("probe_form POST value=%r", value)
    return f"收到：{value}"


if __name__ == "__main__":
    scheduler.start()
    app.run(host="0.0.0.0", port=5252, debug=False)
