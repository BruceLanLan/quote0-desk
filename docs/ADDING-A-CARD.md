# 加一张新卡

`docs/DEVICE-FACTS.md` 是工程日志，记录的是"设备真实行为是什么"；这份文档回答的是另一个问题——"我想加一张卡，该改哪几个文件"。

## 契约：`cards/<name>.py` 只需要一个 `build()`

```python
def build() -> dict:
    ...
```

返回的 dict 有两种形状，`push.py` 靠有没有 `"png"` 键判断走哪条路：

- **Text API**（大多数信息类卡片走这条）：返回 `{"data": {...}, "alias": "...", "link": "..."}`，`data` 用 `canvas.template.simple_data(title=..., message=..., footer=...)` 生成。设备端原生支持 `\n` 换行和自动折行，不用自己算断行。
- **Image API**（需要逐像素控制的卡片，比如爻线、九宫格、ASCII 造型）：返回 `{"png": ..., "alias": "...", "link": "..."}`，`png` 是 `render.base.to_data_url(img)` 的输出（`img` 是一张 `render.base.new_canvas()` 画出来的 296×152 `PIL.Image`）。

两条路都要有的字段：

- `alias`：`task_alias`，出现在 Dot App 的任务记录里，起个能一眼认出是哪张卡的名字。
- `link`：要不要接 NFC 交互，接就用 `config.nfc_base_url()` 拼 `f"{base}/t/<action>" if base else ""`；不接交互（纯展示卡，比如状态灯、时间胶囊）就留空字符串，这是预期行为，不是漏填。

## 最小例子（Text API）

```python
# cards/hello.py
from canvas.template import simple_data

def build() -> dict:
    data = simple_data(title="Hello", message="这是一张最简单的卡", footer="")
    return {"data": data, "alias": "hello", "link": ""}
```

```bash
python3 cli.py push hello
```

## 需要 NFC 交互？在 `server.py` 加一个路由

```python
@app.route("/t/hello_tap", methods=["GET", "POST"])
def t_hello_tap():
    # 1. 执行这次贴一下应该发生的动作（写状态、切换标记……）
    # 2. push_card("hello") 立刻把新内容推回屏幕
    result = push_card("hello")
    log.info("hello_tap push=%s", result)
    return jsonify({"push": result})
```

对应地，`cards/hello.py` 的 `link` 改成：

```python
from config import nfc_base_url

def build() -> dict:
    base = nfc_base_url()
    link = f"{base}/t/hello_tap" if base else ""
    ...
    return {"data": data, "alias": "hello", "link": link}
```

## 数据逻辑放 `providers/`，不要塞进 `cards/`

`cards/*.py` 只管"拿数据 → 拼成 API 要的形状"，真正的计算/状态读写放 `providers/<name>.py`（参照 `providers/todo.py`、`providers/liuyao.py`）。这样 `cli.py`、`server.py`、测试脚本都能直接调用 provider 的函数而不用绕过卡片层。

## 想加进自动轮换？

```bash
python3 cli.py auto-cards proverb status todo hello   # 把新卡名加进列表
python3 cli.py arm
```

## 涉及个人路径怎么办

如果新卡要读某个本地项目/文件（参照 `providers/beacon.py`、`capsule.py` 的做法），不要把路径写成模块顶部的常量——那是早期做法，2026-08-04 之后已经全部搬进 `config.json`。正确做法是在 `config.py` 的 `DEFAULTS` 里加一项（默认值就是你自己机器上的路径，别人 clone 了改配置就行，不用碰源码），provider 里用 `config.path_setting("你的键名")`（单个路径）或 `config.path_list_setting("你的键名")`（路径列表）读，两个函数都会自动 `expanduser` 并在值为空时退回默认值。读不到文件时要优雅降级（返回"暂无数据"而不是抛异常）。加完记得：`server.py` 的 `_EXPOSED_KEYS` 加一行让设置页能读写，`templates/settings.html`「路径配置」卡片加一个输入框，README 的「自己部署：需要改的几处」一节同步一行。

## 让新卡出现在控制台

`server.py` 的 `CARDS` 字典（`{key: 中文名}`）是唯一的权威来源——`/api/cards` 从这里读，加了才算存在。但**只加 `CARDS` 是不够的**：`templates/index.html` 的首页把卡片按用途分组展示（互动卡片/记录与提醒/信息展示/Hermes 集成），分组信息不是自动推导的，是前端 JS 里手写的两处：

- `CARD_META[key]`：图标 + 一句功能说明，不加的话会退回默认的 📎 图标和空说明，不会报错
- `CARD_GROUPS[].keys`：决定这张卡归到哪个分组标题下——**这一步不能漏**，没出现在任何分组的 `keys` 数组里的卡，即使在 `CARDS`/`CARD_META` 里都注册了，也不会在首页渲染出来（`buildCardList()` 只遍历 `CARD_GROUPS`，不会兜底遍历 `CARDS` 里剩下的键）

`templates/settings.html` 的「轮换哪些卡」勾选列表是直接遍历 `CARDS` 生成的，不受 `CARD_GROUPS` 影响，加了 `CARDS` 就会出现，这点跟首页不一样。

## 卡片需要专属控件（不只是"推一下"）？

`buildCardList()` 默认给每张卡渲染一行统一样式（图标+说明+推送按钮）。如果新卡需要额外交互——参照换壁纸卡的文件上传按钮——两处要改：

- `templates/index.html` 里 `renderCardRow()` 按 `key` 特判，插入专属的 HTML（输入框/按钮/状态展示），参照 `key === 'wallpaper'` 那段
- 专属交互如果要落状态到服务端（不是简单调用 `push_card()`），在 `server.py` 加对应的 `/api/<name>/...` 路由，不要塞进通用的 `/api/push` 里——参照 `/api/wallpaper/upload`、`/api/wallpaper/reset`、`/api/wallpaper/status` 三条

大多数卡不需要这一步，纯展示或纯 NFC 触发的卡用默认行就够。

## 检查清单

- [ ] `build()` 返回的 dict 有 `alias`，`link` 要么是真实 NFC 地址要么是空字符串（不是 `None`）
- [ ] 新增的本地路径配置项放进 `config.py` 的 `DEFAULTS`、用 `path_setting`/`path_list_setting` 读，读不到时不崩溃
- [ ] 需要 NFC 的话，`server.py` 的路由和 README 的「NFC 回调服务」路由表都加了对应行
- [ ] `server.py` 的 `CARDS` 字典加了一行；`templates/index.html` 的 `CARD_META` 和某个 `CARD_GROUPS[].keys` 也加了，否则首页看不到这张卡
- [ ] `python3 cli.py push <name>` 跑一遍，`python3 cli.py snapshot out.png` 确认真机渲染符合预期
- [ ] API Key / 设备序列号 / 局域网信息全部走环境变量或占位符，`git grep` 一下确认没有硬编码进新文件
