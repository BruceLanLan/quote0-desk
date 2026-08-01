# quote0-desk

给 [Quote/0](https://dot.mindreset.tech/developers) 墨水屏做的桌面装置服务。
同厂商 [pocket-prophet-dashboard](https://github.com/BruceLanLan/pocket-prophet-dashboard)
（Rand/0 口袋先知）的姊妹项目，但架构不同——Quote/0 常联网、走官方 REST API，
不是局域网直连；296×152 横屏黑白，不是 200×200 方屏；最大的区别是**有 NFC**：
手机贴一下能打开当前内容绑定的 `link`，构成"屏幕出题 → 手机贴一下 → 服务
干活 → 屏幕变化"的闭环，不只是单向数据面板。

设备真机契约（槽模型、字号下限、Canvas `\n` 处理等实测结论）见
[`docs/DEVICE-FACTS.md`](docs/DEVICE-FACTS.md)，是本项目所有设计决策的事实依据，
遇到"为什么这么写"先去那份文档找证据。

## 快速开始

```bash
pip install -r requirements.txt

export DOT_API_KEY=dot_xxx...     # Dot App → More → API Key 创建
# export DOT_DEVICE_ID=xxxxxxxx   # 可选：账号下只有一台设备时会自动发现，不用填

python3 cli.py hello               # 推一张最简卡，验证链路通不通
python3 cli.py status              # 看设备在线状态
python3 cli.py snapshot out.png    # 下载当前屏幕的真实渲染图（开发期最重要的自查手段）
python3 cli.py push <card_name>    # 推 cards/ 下某张卡，比如 python3 cli.py push pet
python3 cli.py set-todo "今天要做的事"
```

**关键前提**：Quote/0 的官方 API 只能"更新" Dot App「内容工坊」里预先建好的
内容槽，不能凭空创建新内容项，而且**账号的 loop 槽位有硬上限（3 个）**。
本项目实际能用的是其中 2 个：**文本 API**（Text）+ **图片 API**（Image），
第 3 个槽由用户自己留给官方内容，Canvas API 已经不在架构里（详见
`docs/DEVICE-FACTS.md` 08-01 那节的重写说明）。内容工坊加好槽之后不用
告诉这边具体的 key——`GET /loop/list` 会自动发现，按 `type` 字段区分。

## NFC 回调服务

```bash
python3 server.py   # Flask，默认监听 0.0.0.0:5252
```

每次推送时把 `link` 字段设成 `http(s)://<能被手机访问到的地址>/t/<action>`，
手机贴一下 NFC → 打开这个 URL → 对应路由执行动作 → 立即把新内容推回屏幕。
`link` 目前必须是手机连得到的地址（跟设备同一 WiFi 的局域网 IP，或者公网/
内网穿透地址）——纯 `localhost` 手机连不上。

| 路由 | 触发效果 |
|---|---|
| `/t/counter_tap` | M2 验证用的计数器，贴一下 +1 |
| `/t/todo_toggle` | 今日一件事打卡，切换完成状态 |
| `/t/proverb_next` | 箴言机换下一句 |
| `/t/qiantong` | 签筒抽一签（摇卦或奇门二选一，真随机） |
| `/t/pet_pat` | 摸摸屏上宠物，触发一次性"精神"反应 |
| `/t/ping` | 探测用，只记日志不推送 |

## 内容卡

| 卡 | 命令 | 说明 |
|---|---|---|
| 箴言机 | `push proverb` | 种子缓存里挑一句，NFC 换下一句；不接模型生成，避免"刷一次屏调一次模型" |
| 摇卦 | `push liuyao` | `secrets` 真随机抛铜钱起卦，移植自 pocket-prophet-dashboard |
| 奇门遁甲 | `push qimen` | 九宫格排盘，移植自 pocket-prophet-dashboard |
| 签筒 | `push qiantong` | 摇卦/奇门二选一，NFC 触发版 |
| Claude Code 状态灯 | `push status` | 扫描 `~/.claude/projects` 的转录文件，今日 token/成本估算 + 活跃指示 |
| 屏上宠物 | `push pet` | ASCII 造型（移植自 claude-buddy），状态由真实行为驱动：commit = 喂食，长时间不动 = 饿，NFC 贴一下 = 摸摸 |
| 今日一件事 | `push todo` / `set-todo "..."` | 单条每日承诺，NFC 打卡 |
| 时间胶囊 | `push capsule` | 本机 git 仓库历史里"一年前/一个月前/一周前的今天"提交 |
| 实盘信标 | `push beacon` | 只读展示 lighter-scalper 持仓 + stock-radar 最新信号，不导入其代码/密钥 |

日课/时辰盘（干支排盘卡）计划中但尚未实现。

## 架构

```
quote0-desk/
  dot.py            # 官方 REST API 薄客户端：devices/status/settings/text/image/canvas
  config.py         # 配置读写；API Key 只认环境变量，绝不落 config.json
  cards/            # 内容源：build() → {"data", ...} 走 Text API，或 {"png", ...} 走 Image API
  canvas/            # 文本卡的数据形状（title/message/footer 三段式，喂给 Text API）
  render/            # 需要逐像素控制的卡（爻线、九宫格、ASCII 宠物）本地 PIL 渲染
  providers/         # 纯数据逻辑，不碰渲染/推送
  server.py          # Flask：NFC 回调 /t/<action>
  push.py            # cli.py 和 server.py 共用的"按卡名推送"逻辑
```

设备只给了 2 个能用的槽（**Text API** + **Image API**，第 3 个槽上限被
用户自留的官方内容占了，Canvas API 已经出局），但内容卡有 9 张。架构上
不是"每张卡一个槽"，而是**同一个槽被不同卡分时复用**——由服务这边的调度
决定当前该显示哪张卡，设备侧只是被动接受更新。设备原生的自动轮转
（`interval.powerMs`）已调到官方上限（12 小时）来避免它在没推送的间隙自己
把画面转走，节奏完全交给这边控制（编排/调度落在 M6，见下）。

槽位数量限制的是"同时能露出几张脸"，不限制卡的总数——加第 10 张卡不花
任何槽位成本，调度器照样轮。

## 调度器（M6）

`scheduler.py` 是个后台 daemon 线程，按 `config.json` 的 `auto_push_interval_minutes`
周期轮换推送 `auto_push_cards` 列表里的卡（不含 `qiantong`/`counter`，那些是
NFC 触发的，不参与自动轮换）。默认关闭，需要显式布防：

```bash
python3 cli.py auto-cards proverb status todo capsule beacon liuyao qimen pet
python3 cli.py arm            # 打开自动轮换
python3 cli.py disarm         # 关闭
python3 server.py             # 常驻运行，调度线程随 Flask 一起启动
```

也可以直接打 `GET/POST /settings` 查看或改这三项配置（`auto_push_enabled` /
`auto_push_interval_minutes` / `auto_push_cards`）。

## 状态

M0（真机契约验证）到 M6（调度器 + 隐私审查）已完成，见 `docs/DEVICE-FACTS.md`
的实测记录。

NFC 的 `link` 语义（贴一下打开的是否确实是"当前内容"绑定的 URL，而非固定地址）
是本项目的立足点假设，仍待用户真机验证——这条不成立，闭环概念就要重新讨论。

## 仓库状态

当前私有。API Key 和设备序列号一律走环境变量/占位符，不落库；`docs/DEVICE-FACTS.md`
的隐私审查记录一节有本次 `git grep` 扫描结果。计划做完、真机验证过 NFC 闭环后
再决定是否公开。
