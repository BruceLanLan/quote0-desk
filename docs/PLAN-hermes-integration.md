# quote0-desk × Hermes Studio 整合规划（T6 规划交接单，2026-08-04，Opus 5 规划）

## 目标

判断 quote0-desk 与 Hermes 生态（Hermes Studio / Hermes Agent）整合的技术形态，
给出一条**在对方完全不回应的情况下也 100% 保留价值**的主线，并附一份可以
真的拿去跟 JPeetz 谈的接触方案。本轮产出规划与事实基线，不写实现代码。

## 一、事实核查结果

### A. 查证过的事实（有源码/API 出处）

**F1 · 本机现状。** `~/.hermes/hermes-agent/` 存在完整源码树，`~/.hermes/config.yaml`
（16.9KB）、`auth.json`、`cron/jobs.json`（6.2KB，里面已有历史任务）都在，最后活动
2026-06-23。但 CLI 已坏：`~/.local/bin/hermes` 报
`venv/bin/python3: bad interpreter: No such file or directory`（venv 的 python 链接失效，
典型的 Homebrew Python 升级后遗症）。gateway `127.0.0.1:8642` 和 Studio `127.0.0.1:3000`
均未在跑（curl exit 7）。**Hermes Studio 本机没有安装**（`~/Hermes-Studio` 不存在）。

**F2 · Studio 是薄代理，不是执行方。** `src/routes/api/hermes-jobs.ts` 的 GET/POST 就是
把请求原样转发到 `${HERMES_API}/api/jobs`（默认 `http://127.0.0.1:8642`）。README 原文：
"The gateway already runs the jobs. Hermes Studio is the control plane that makes them
manageable without a terminal."

**F3 · Studio 的投递渠道是硬编码的三项。** `src/screens/jobs/create-job-dialog.tsx:17`
与 `src/screens/jobs/edit-job-dialog.tsx:18` 都是：

```ts
const DELIVERY_OPTIONS = ['local', 'telegram', 'discord'] as const
```

渲染处（create 第 325 行、edit 第 348 行）还有一处 `option === 'telegram' || option === 'discord'`
的 needsGateway 判断。**README 宣称的 "Telegram, Discord, Slack, or Signal" 在这个下拉里
并不存在**——实际只有 local/telegram/discord。加一个渠道 = 改两个文件各两处，不到 10 行。

**F4 · hermes-agent 有一等公民的平台插件机制，明写「推荐第三方走这条」。**
`gateway/platforms/ADDING_A_PLATFORM.md` 开头：

> ## Plugin Path (Recommended for Community/Third-Party)
> Create a plugin directory in `~/.hermes/plugins/` … The adapter inherits from
> `BasePlatformAdapter` and registers via `ctx.register_platform()` in the `register(ctx)`
> entry point. This requires **zero changes to core Hermes code**.
> The plugin system automatically handles: adapter creation, config parsing, user
> authorization, **cron delivery**, send_message routing, system prompt hints, status
> display, gateway setup, and more.

注册表在 `gateway/platform_registry.py`（`PlatformEntry` dataclass）。
**Telegram / Discord / Slack / Signal 自己就是插件**——`plugins/platforms/` 下有
dingtalk、discord、email、feishu、google_chat、homeassistant、irc、line、matrix、
mattermost、ntfy、photon、raft、simplex、slack、sms、teams、telegram、wecom、whatsapp
共 20 个目录。

**F5 · 最贴近 Quote/0 的现成样板是 ntfy 插件。** `plugins/platforms/ntfy/` 只有
`plugin.yaml` + `adapter.py`（593 行）+ `__init__.py`（3 行），纯 httpx 无 SDK，作者是社区
用户 `sprmn24`。它的 `register(ctx)` 里有两个正是"第五个投递渠道"所需的钩子：

```python
cron_deliver_env_var="NTFY_HOME_CHANNEL",   # deliver=ntfy 的 cron job 路由到这个 channel
standalone_sender_fn=_standalone_send,      # cron 与 gateway 不同进程时的带外投递
```

`ADDING_A_PLATFORM.md` 对 `cron_deliver_env_var` 的说明是"without editing
`cron/scheduler.py`'s hardcoded sets"，对 `standalone_sender_fn` 的说明是"Without this,
a `deliver=<name>` job fires correctly but the actual send returns
`No live adapter for platform '<name>'`"。两个都实现 = cron 端到端。

**F6 · 「贴一下批准工具调用」在 Hermes 侧是官方钩子，不是 hack。**
`BasePlatformAdapter` 定义了
`send_exec_approval(chat_id, command, session_key, description, metadata) -> SendResult`
（"Render dangerous-command approval as Approve/Deny buttons. Inbound dispatch routes to
`tools.approval.resolve_gateway_approval`"）；解析端在
`tools/approval.py:729 resolve_gateway_approval(session_key, choice, resolve_all=False)`。
discord / feishu / telegram / teams / slack / matrix / qqbot / whatsapp_cloud 八个适配器
都已实现。同一套还有 `send_clarify()`（多选题变可点按钮）。

**F7 · Studio 侧的「待审批列表」只存在于浏览器里。** `src/lib/approvals-store.ts` 是
in-memory `Map` + `sessionStorage`（注释原文："persisted to sessionStorage so approvals
survive soft navigations but clear when the tab closes"），数据由 SSE 事件喂进来。
Studio 的 `/api/approvals/:id/approve` 只做两件事：优先打
`${HERMES_API}/api/sessions/{sessionKey}/approve`，否则退化成往会话发一条 `/approve`
聊天命令（scope 拼成 `/approve` / `/approve session` / `/approve always`）。
**没有任何「列出当前待审批」的 REST 端点。**

**F8 · Studio 的鉴权模型。** `src/server/auth-middleware.ts`：没设 `HERMES_PASSWORD` 时
`isAuthenticated()` 直接 `return true`；`requireLocalOrAuth()` 在无密码时放行
127.0.0.1 / ::1 / 100.x（Tailscale）/ 192.168.x / 10.x。CSRF 防护只有
`requireJsonContentType`。→ 默认配置下，本机任何程序零凭据即可读写 Studio 的 `/api/*`。

**F9（2026-08-04 真机验证后修正，原文有错）· gateway 的 REST 面。**
`/api/sessions`（含 `/{id}/messages`、`/fork`、`/chat`、`/chat/stream`）、
`/api/jobs`、`/api/jobs/{id}`（GET/PATCH/DELETE）、`/api/jobs/{id}/pause|resume|run`、
`/api/cron/fire` 都实测存在。**原文写的"一个返回 gateway state 的状态接口"不存在
——`GET /api/status` 实测 404，这是没验证就写的推测，已被推翻。** 真实的只读状态面是：

- `GET /health`：**不需要鉴权**，返回 `{"status":"ok","platform":"hermes-agent","version":"0.17.0"}`。
  这个形状正好对应 buddy-bridge 那种"不带 token 只回健康检查"的设计，`providers/hermes.py`
  判定 `available` 应该用这个端点。
- `GET /health/detailed`：需鉴权，返回 `gateway_state` / `platforms{}` / `active_agents` /
  `gateway_busy` / `pid`。

**新增硬前提，原文完全没提到：`API_SERVER_KEY` 是必需的，回环地址也不放过。**
只设 `API_SERVER_ENABLED=true` 起不来，实测报错：
`Refusing to start: API_SERVER_KEY is required for the API server, including
loopback-only binds on 127.0.0.1`。`providers/hermes.py` 需要一条读 key 的路径，
照 `providers/buddy.py` 读 `~/.buddy-bridge/token` 的纪律：只读、不落库、不打日志。

**验证点精度修正**：裸 `GET /api/jobs` 对 paused/disabled 的 job 返回 `{"jobs": []}`，
必须加 `?include_disabled=true` 才能拿到全量，跟磁盘上 `cron/jobs.json` 对上。第 2 步
写卡片逻辑时不能假设默认列表就是全量。

**F10 · 插件分发完全不经过 Studio。** `hermes plugins install <owner>/<repo> --enable`
直接从任意 GitHub 仓库装（Studio README 自己举的例子是
`hermes plugins install Xquik-dev/hermes-tweet --enable`）。生态元数据是仓库根部的
`.hermes-eco.json`（`resource_type: integration`）+ `skill.json`（含
`install.openclaw` 命令字段）+ 可选 `dashboard/manifest.json`（`slots: ["tools"]`）。
现成第三方样板：`Xquik-dev/hermes-tweet`（MIT，23 星）。

**F11 · Hermes Studio 仓库的真实活跃度。** JPeetz 个人开发者，contributors 只有
4 个：JPeetz 134 commits、github-actions[bot] 3、kriptoburak 1、nandanadileep 1。
295 星 / 60 fork / 4 个 open issue / MIT / 无 Discussions。**最后一次 push 是
2026-07-03，距今约一个月。** 外部 PR 共 8 个，合并 2 个：#6（KaTeX 渲染，功能 PR，
开着 25 天后合并）、#10（纯文档：给 hermes-tweet 写一段插件示例，2 天合并）。
其余 6 个关闭未合，其中 #7（forward gateway bearer token）开启后 **14 分钟**关闭、
#13（v0.19 bearer + 响应格式兼容）开启后 **2 分钟**关闭，两个都没有维护者评论；
随后 2026-07-03 维护者自己提交了 `feat(deploy): add Hermes Agent v0.18 compatibility support`。
issue 侧：#16（2026-07-31 提）**4 分钟**被回应并关闭；#11、#14（同一个 KaTeX 依赖
导致 docker build 失败 / 启动 500）分别开了 4 周和 1 周无人处理。

**F12 · 上游主仓的量级。** `NousResearch/hermes-agent`：225,122 星 / 43,660 fork /
**27,406 个 open issue** / MIT / 今天仍在 push。

**F13 · Hermes Studio 是 `outsourc-e/hermes-workspace` 的 fork**（LICENSE 里保留了
原作者 Eric 的版权行），MIT。

### B. 推测判断（未查证，明确标注）

**I1（推测）：维护者对「碰核心代码的 PR」倾向自己重写，对「文档/示例类 PR」倾向合并。**
样本只有 8 个 PR，n 很小；#7/#13 的秒关也可能是因为他本地已有同样的修改。不要当定论用，
但足以支撑"先开 issue 探路、别一上来甩一个大 PR"这个策略。

**I2（推测）：一个月没提交代码 ≠ 弃坑。** 依据是 issue #16 在 4 分钟内被处理（人还在
看通知），但 #11/#14 这种构建级 bug 挂着没修，指向"在看但没时间写代码"。因此
**开 issue 得到回应的概率 > PR 被合并的概率**。

**I3（推测）：把 `DELIVERY_OPTIONS` 改成从 gateway 动态拉取是可行的**——gateway 的状态
接口会返回 connected platforms（F9），但我没有验证过它在 job 场景下的字段形状，也没有
验证过 gateway 是否暴露"这个平台支持被 cron deliver"这一位信息。作为提案可以写，作为
承诺不行。

**I4（推测）：quote0-desk 对 Hermes 生态的独特价值是"物理终端"。** 现有 20 个平台适配器
全是软件消息通道（IM/邮件/推送），没有一个是**电子墨水屏 + NFC 物理回执**。
homeassistant 最接近但方向相反（Hermes 控制家居，不是家居设备回执给 Hermes）。这个"生态
里唯一一个"的判断基于 `plugins/platforms/` 的 20 个目录名，没有逐个读源码确认。

### C. 第 1 步真机执行记录（2026-08-04，事实，非推测）

**根因跟 F1 猜的不一样。** 不是 Homebrew 升级 python@3.14，是 **uv 管理的
CPython 3.11.15 被 prune 掉了**：`venv/bin/python -> ~/.local/share/uv/python/
cpython-3.11-macos-aarch64-none/bin/python3.11`（不存在），`pyvenv.cfg` 里
`version_info = 3.11.15, uv = 0.10.12`。`~/.local/share/uv/python/` 当时只剩
3.10.19 和 3.13.12，整个目录 7 月 22 日被重建过，3.11 那份被清掉了。

**修法不是重建 venv，是 `uv python install 3.11.15`。** site-packages 里有
3015 个 `*.cpython-311-darwin.so`（308MB，hermes_agent 0.17.0 editable），换
3.12/3.13 重建等于全部重下重编。`uv python install 3.11.15` 只是把这个具体
patch 版本的解释器重新装回 uv 的 python store（连带悬空软链一起修好），**venv
目录本身一个字节没动**，`pip install -e .` 都不需要跑。修完验证：
`venv/bin/python3 -V` → `3.11.15`；`hermes --version` → 能跑；
`hermes plugins list` 列出 75 个插件，含 `plugins/platforms/` 全部 20 个，
命名规则是 `<name>-platform`（比如 `telegram-platform`、`ntfy-platform`）——
**证实第三节的插件应命名为 `quote0-platform`**。

`curl 127.0.0.1:8642/api/jobs?include_disabled=true` 返回 3 个 job，跟磁盘
`cron/jobs.json` 的 ID/name 集合完全一致，验证点 1 通过。

**一个需要用户知道的副作用：一个 once 类型的 job 被验证过程弄成永久不可达。**
启动 gateway 前，3 个 job 全部 `enabled=True` 且 `next_run_at` 停在 5 月（逾期未跑，
gateway 一起来就会立刻触发）。为了不在验证阶段意外真的跑一个真实 agent 回合
（其中 `agent-personas-continuation` 是 `no_agent=False`、带 1313 字 prompt 和
工具权限的真实任务，workdir `~/agent-personas-dev`），验证前先 `hermes cron pause`
了全部三个，验证后 `resume`。`enabled/state/paused_at` 都恢复原样，但 **resume 会
重算 `next_run_at`**，而 `agent-personas-continuation` 是 once 类型，`run_at` 已经
过去 77 天，远超调度器 `ONESHOT_GRACE_SECONDS = 120`（2 分钟）的宽限——**这个 job
现在 `next_run_at = None`，永远不会被自动触发了**。另外两个（`daily-tracking`
`weekly-optimization`）是循环任务，重算后的下次触发时间是 2026-08-05 10:00 和
2026-08-09 14:00，正常，但目前没有任何东西让 gateway 常驻（`~/Library/LaunchAgents`
下没有 hermes 相关项），到时间点 gateway 没在跑就还是不会触发。

**用户决定（2026-08-04）：不处理，不再碰本机这个 hermes-agent 实例——用户准备
重新装一遍、重新养 agent。** 所以这个 once 任务的补跑/重排问题就此作废，不用再
跟进。后续步骤（第 2/3 步）针对的是 hermes-agent 的 API 形状（`/health`、
`/api/jobs`、插件注册机制），这些在重装后应该还是一致的（同一份软件），但
**最终真机验证需要等用户重装完成之后才能对着新实例跑一遍**，本机当前这个
（已经被 uv python install 修好、但用户即将丢弃的）实例只用来验证 API 形状，
不再作为长期开发环境。

**发现一个可能对第 5 步接触材料有用的线索（未验证，标注为推测）**：gateway 的
路由表里有 `POST /v1/runs/{run_id}/approval` 和 `GET /v1/runs/{run_id}/events`，
但 Hermes Studio 的 approve 按钮打的是 `/api/sessions/{sessionKey}/approve`——
这条路径在 0.17 的路由表里根本不存在。如果这个观察在真实 pending approval 场景下
复现，那是一个可复现的 Studio↔gateway 互操作 bug，比"能不能加个渠道"的功能请求
更容易开启对话（帮对方修一个真 bug，而不是伸手要功能）。**这条没有被真实验证
过——只是看路由表对不上，没有真的走一遍 approval 流程确认 Studio 那边会报错**，
第 5 步动手前要先补这个验证，不能直接当结论用。这条发现对第七节「NFC 批准
exec approval」的安全签字要求没有任何改变，仍然在本轮范围外。

---

## 二、整合形态：六个选项与推荐

| 选项 | 做什么 | 依赖对方吗 | 工作量 | 判断 |
|---|---|---|---|---|
| **A 单向只读** | `providers/hermes.py` 读 gateway `/api/jobs` `/api/status`，推一张"Hermes 任务台"卡 | 否 | 小（照 `buddy.py` 抄纪律） | **做**，保底 |
| **B NFC 触发 job** | 贴一下 → `POST /api/jobs/{id}/run` | 否 | 小 | **做**，但只跑 config 白名单里的 job |
| **C NFC 批准 exec** | 贴一下 = approve 一次工具调用 | 否 | 中 | **本轮不做**，见范围边界 |
| **D quote0 平台适配器插件** | 独立仓库 `hermes-quote0`，`ctx.register_platform(name="quote0", …)` | **否** | 中（ntfy 593 行是上限参照） | **推荐主线** |
| **E 向 Studio 提 PR** | E1 两处数组加 `'quote0'` / E2 改成动态列表 / E3 纯文档示例 | 是 | E1/E3 极小、E2 中 | **E3→E1 顺序做**，E2 只提案 |
| **F 纯设计参考** | 只借鉴审批 UI / cron manager 的交互模式 | 否 | 极小 | 兜底，不作为目标 |

### 推荐：D 为主线，A 为保底，E 为接触材料

**为什么 D 优于「写 providers/hermes.py 读 Studio」：**

1. **方向对了。** A 是"quote0 去偷看 Hermes 在干嘛"；D 是"Quote/0 成为 Hermes 官方
   支持的一种投递目标"。后者才是 F4 那份文档明写欢迎的路径，也才是能拿去跟人谈的东西。
2. **D 一次买到 A/B/C 三件事。** 注册一个平台适配器之后，`send_message` 路由、
   cron `deliver=quote0`、`send_exec_approval` 审批按钮、system prompt hint、
   `hermes gateway status` 显示——按 F4 的说法全都是插件系统自动接上的，不用逐个实现。
3. **D 不需要 JPeetz 点头。** 插件从任意 GitHub 仓库装（F10）。对方哪怕永远不回应，
   用户也拿到一个"Hermes 的 cron job 结果落到墨水屏上"的可运行成果。
4. **D 让 E 变得有意义。** 单独提 E1（给 Studio 下拉加 `'quote0'`）是无效 PR——
   gateway 侧不认识这个渠道名，选了也不会送到。**先有 D，E1 才是一个"改两行就能用"
   的 PR**，这正是最容易被合并的形状。

**为什么这不是「绕开合作」而是「合作的入场券」：** 按 I1/I2 的判断，直接找一个一个月
没写代码的独立维护者谈"我们两个项目整合一下"，大概率石沉大海。带着一段"Hermes 定时
任务跑完，结果出现在一块 296×152 墨水屏上，手指贴一下屏幕内容就换了"的视频去开 issue，
性质完全不同——那是一个已经能跑的生态集成，对方只需要决定"要不要在下拉框里加一行"。
**先做出既成事实，再谈合作**，是这类不对等开源协作里唯一稳的顺序。

### 安全设计决策（写进文档，实现时必须遵守）

- **D1：插件的 send 路径不接受 agent 指定的 `link`。** NFC 回调地址一律由 quote0-desk
  服务端按卡片类型固定生成，agent 只能提供 title / message。理由：agent 会被 prompt
  injection，而"物理卡片 + 手机贴一下"是可信度极高的载体——让 agent 能写 `link` 等于
  给它一个高转化率的钓鱼渠道。这条比软件通道里的同类风险更值得当硬约束。
- **D2：强制来源签名。** 复用现有 footer 约定（`cards/status.py` 的
  `quote0-desk · Claude Code 状态灯` 那种），Hermes 推来的内容一律带
  `Hermes Agent` 字样，屏幕上永远能分辨这条内容是谁写的。
- **D3：身份模型照抄 ntfy。** 固定单一 channel，不从消息内容推导用户身份
  （ntfy adapter 的原话："never derives user identity from publisher-controlled fields"）。
- **D4：可选依赖纪律照 `providers/buddy.py`。** gateway 没跑 = `available: False` +
  优雅降级，永不抛异常。公开仓库的绝大多数使用者没有 Hermes。

---

## 三、对「两个项目方合作」的现实判断

**大概率的合作形式，按可能性排序：**

1. **（最可能）对方在 issue 里表示"cool，欢迎"，然后把 quote0 写进 README 的集成/插件
   示例段落。** 精确先例：PR #10 就是外部贡献者给 hermes-tweet 写了一段插件示例文档，
   2 天合并（F11）。成本对他几乎为零，对我们是官方背书。
2. **（次可能）E1 那个 10 行的下拉框 PR 被合并。** 前提是 D 已经能跑、PR 里附了截图/
   视频、且 diff 只碰那两个文件。风险是 I1——他可能自己重写一遍，那也算赢。
3. **（不太可能）对方主动做更深的对接**（比如 E2 动态渠道列表、或在 Studio 里加一个
   Quote/0 设备面板）。他一个月没写代码，手上还挂着两个没修的构建级 bug（F11），
   不要把计划建立在这个分支上。
4. **（几乎不可能）往 `NousResearch/hermes-agent` 提核心 PR。** 27,406 个 open issue
   （F12），排队成本不可估。**明确不做**——而且 F4 已经给了官方许可的旁路，本来也不需要。

**需要准备的接触材料（按重要性）：**

- **一段 30 秒视频/一组照片**：Hermes cron job 跑完 → 墨水屏刷新 → 手贴一下 → 屏幕变。
  这是唯一无法用文字替代的东西，也是这个项目最强的一击。
- **`hermes-quote0` 仓库本身**：README 第一行就是
  `hermes plugins install BruceLanLan/hermes-quote0 --enable`，附
  `.hermes-eco.json` / `skill.json`（照 F10 的样板），让对方一条命令就能验证。
- **一段 200 字的 quote0-desk 是什么**：强调 I4 那条——生态里 20 个平台适配器全是软件
  通道，这是第一个物理终端；以及 NFC 双向闭环（官方生态 20+ 第三方项目全是单向面板）。
- **E1 的 diff 预览**（先贴在 issue 里，不直接开 PR）：让他看到代价只有 10 行。
- 不要准备的：路线图、合作备忘录、长篇提案。这是一个个人维护者的周末项目，不是公司 BD。

**值不值得投入：** 值得，但要把预期钉死在正确的地方。真正的资产是 D（插件本身），
它的价值不依赖任何人回应；跟 JPeetz 的互动是**上层的一次低成本尝试（预算：写 issue
+ 视频 ≈ 半天，之后不追）**。如果把成功定义成"对方接受合作"，这件事期望值很差；
定义成"quote0-desk 成为 Hermes 生态里可安装的物理终端"，期望值很好。

---

## 四、步骤（按风险与信息增益排序，最不确定的在前）

### 第 1 步：把本机 hermes-agent gateway 跑起来 —— 本轮最大的未知。**已完成，两个验证点都通过。**

整份规划都建立在"gateway 能在这台机器上跑起来"之上，而 F1 显示 venv 已坏、
Studio 根本没装。这一步的信息增益最高、且是所有后续步骤的地基，必须第一个做。

**真实执行结果见第一节「C. 第 1 步真机执行记录」**——根因不是这里猜的
Homebrew python 升级，是 uv 的 python store 被 prune；修法是
`uv python install 3.11.15`，不是重建 venv。产生了一个需要用户决定的副作用
（一个 once 类型的 cron job 变成永久不可达），已在 C 节详细记录，**没有自作主张
处理，等用户决定**。

- 修 venv：`~/.hermes/hermes-agent/venv` 的 python 链接失效，重建 venv 并
  `pip install -e .`；在 `~/.hermes/.env` 里设 `API_SERVER_ENABLED=true`；
  `hermes gateway run`。
- → **验证点 1**：`curl -s 127.0.0.1:8642/api/jobs` 返回 JSON，且内容能跟
  `~/.hermes/cron/jobs.json` 里已有的历史任务对上（不是空数组）。
- → **验证点 2**：`hermes plugins list` 能列出 `plugins/platforms/` 下的适配器
  （确认插件加载器活着——这是第 3 步的前置）。
- → **卡住怎么办**：a) 改走 Studio README 的 docker compose 路径（需要
  `ANTHROPIC_API_KEY`，要先跟用户确认愿不愿意为此消耗 API 额度）；b) 两条都失败就
  **停在这里向用户报告**，不要靠 mock fixture 硬推第 2-4 步——那样每个"验证点"都是假的，
  违反本项目一贯的"真机验证"纪律。
- **需要用户决定的事**：修 venv / 装 Docker 会改动 `~/.hermes` 之外的环境，且 gateway
  跑起来后会持有用户的 `auth.json`。这一步开始前先说明清楚，照 `PLAN-next-round.md`
  对"仓库公开"的处理方式——不替用户按按钮。

### 第 2 步：`providers/hermes.py` + `cards/hermes.py`（只读保底）。**代码已完成，真机验证待补。**

严格照 `providers/buddy.py` 的结构与纪律：`fetch()` 返回
`{"available": True/False, ...}`，永不抛异常，超时 3 秒。读 **gateway 直连**
（`127.0.0.1:8642`）而不是 Studio——少一层、不依赖 Studio 装没装、F8 那套鉴权模型也
不用碰。

**跟原计划的两处出入**：一是卡片内容改成只展示任务列表（名字+schedule），
没有做"活跃 crew / token 与成本"——那些字段没有在真机验证里出现过，F9 修正后
只确认了 `/api/jobs` 和 `/health`，不假设没验证过的字段存在，等真拿到字段
形状再加。二是先探 `/health`（免鉴权）区分"gateway 没开"和"没配
`HERMES_API_KEY`"两种不可用原因，这是 F9 修正后新增的必要前置，原计划没有。

- → **验证点（已做，mock 数据）**：`fetch()` 在 gateway 未启动时返回
  `available: False, reason: "gateway_not_running"`；`cards/hermes.py` 用
  三个真机验证时见过的真实 job（`agent-personas-continuation` 等）mock 出
  `available: True` 的情况，渲染正常；job 缺 `name`/`schedule` 字段时防御式
  降级，不崩溃。三条路径 `python3 -m py_compile` + 手动跑通。
- → **验证点（未做，等用户）**：真机对着一个真的在跑的 gateway 推一次，
  屏幕上的 job 名字与 `curl /api/jobs` 的返回一致——用户决定重装
  hermes-agent，本轮没有可用于最终验证的真实实例，这条留到重装完成后补。

### 第 3 步：`hermes-quote0` 插件骨架 —— 最小可用的 send 路径

**独立新仓库**（不是 quote0-desk 里的目录），照 `plugins/platforms/ntfy/` 的两文件结构：
`plugin.yaml` + `adapter.py`，`register(ctx)` 调 `ctx.register_platform(name="quote0", …)`。
`send()` 里调 quote0-desk 已有的 `POST /api/push`（或直接 `dot.push_text`），
遵守 D1/D2/D3。

- → **验证点**：gateway 里让 agent 用 `send_message` 发到 quote0，**墨水屏内容真的变**，
  且屏幕上带 `Hermes Agent` 签名行、`link` 是我们服务端固定生成的那个。
- → **卡住怎么办**：`register_platform` 的实际签名/`Platform` 枚举要求跟
  `platform_registry.py` 的注释有出入时，以 `plugins/platforms/ntfy/adapter.py` 的
  实际调用为准（它是能跑的活样板）。仍失败就退到"插件只提供 tool 不注册 platform"
  （hermes-tweet 那种形态），代价是失去 cron deliver 与 exec approval 两个钩子——
  这会让第 4 步降级成"靠 prompt 里写'然后推到我的 Quote/0'"，**仍然可用，但不再是
  第五个渠道**，要如实记录这个降级。

### 第 4 步：cron 投递 —— 「第五个渠道」的可运行证据

补 `cron_deliver_env_var="QUOTE0_HOME_CHANNEL"` 与 `standalone_sender_fn`（F5）。

- → **验证点**：建一个每分钟跑一次的 cron job，`deliver=quote0`，**不碰 Studio、不改
  任何 Hermes 核心文件**的前提下，屏幕上出现 job 结果。同时录下第三节要的那段视频。
- → **卡住怎么办**：出现 `No live adapter for platform 'quote0'` 就说明
  `standalone_sender_fn` 没接上（F5 明确点名了这个失败信号），照 ntfy 的
  `_standalone_send` 对齐签名。
- **这一步跑通 = 本轮的核心产出。** 后面所有对外动作都是它的衍生品；即使第 5 步
  全盘落空，项目已经净赚一个新能力。

### 第 5 步：接触 Hermes Studio（预算半天，之后不追）

在 `JPeetz/Hermes-Studio` 开一个 issue（不是 PR），标题走
"Integration: Quote/0 e-ink device as a cron delivery target"这类描述性写法。内容：
视频/照片 + 一条 `hermes plugins install` 命令 + F3 那两处 `DELIVERY_OPTIONS` 的 10 行
diff 预览 + 一句"要的话我提 PR，不要也完全不影响，插件已独立可用"。

- → **验证点**：issue 收到任何回应（评论/label/关闭）。有回应且是正面的 → 按对方偏好
  提 E1（下拉框）或 E3（README 示例段）。
- → **卡住怎么办（两周无回应）**：**不追、不 at、不重复开**。转去
  a) `.hermes-eco.json` / `skill.json` 走生态注册表（F10）——这才是插件真正的分发渠道，
  本来就不经过 Studio；b) `PLAN-next-round.md` 第 6 步的 Quote/0 官方 co_create showcase。
- 注意：**先别提 E2（动态渠道列表）**。那是 I3，我没验证过 gateway 会不会告诉你
  "哪些平台支持 cron deliver"；作为 issue 里的一句建议可以，作为 PR 不行。

### 第 6 步（可选，需另行签字）：NFC 触发 cron job

`/t/hermes_job/<name>` → `POST /api/jobs/{id}/run`（F9）。**只允许 `config.json` 里
预先声明的白名单 job**，NFC 路径不接受任意 job id、不接受自由文本 prompt。

- → **验证点**：贴一下，Studio/`/api/jobs` 里那个 job 的 last-run 时间更新，
  结果按第 4 步的链路回到屏幕上——这就是完整的双向闭环。
- 这一步风险低于第 7 步（job 是用户自己预先写好的 prompt，不是 agent 临时要求的
  任意命令），但仍会真的花 token / 真的执行动作，**要用户明确点头才做**。

### 第 7 步（本轮不做，只记录结论）：NFC 批准 exec approval

`PLAN-next-round.md` 末尾那条候选功能。本轮的唯一贡献是**把"技术上怎么做才是对的"
钉死**，以免将来签字时选错实现：

- **正确实现**：用 F6 的官方钩子——适配器实现 `send_exec_approval()`，Hermes 会把
  command 原文 + `session_key` 直接送到我们手上；NFC 回调调用
  `resolve_gateway_approval(session_key, choice)`。屏幕上显示的命令和被批准的命令
  由同一条消息保证一致。
- **错误实现（明确否决）**：走 Studio 的 `/api/approvals/:id/approve`。按 F7，Studio 的
  待审批状态只活在浏览器的 sessionStorage 里，没有任何"列出待审批"的 REST 接口——
  quote0-desk 只能自己挂 SSE 维护一份镜像，而镜像与 gateway 真实队列之间存在时间差：
  **屏幕上印着 A 命令，手指贴下去时 FIFO 队列头部可能已经是 B 命令**（`resolve_gateway_approval`
  默认就是"解析最老的那个"）。这是一个真实的 TOCTOU 缺口，不是理论洁癖。
- 即便走了正确实现，"贴一下会真的授权一次工具调用"这个**安全签字问题依然独立存在**，
  且因为 Hermes Agent 的工具面比 buddy-bridge 展示的更广（shell / 文件 / MCP / 20 个
  消息平台的发送权限），后果比原方案更重。签字条件至少要包含
  `PLAN-next-round.md` 已列的两条（排除高风险工具、README 写清权限含义），
  再加一条：**`always` scope 一律不走 NFC 路径**，NFC 只能对应 once。

---

## 五、范围边界（这一轮明确不做的事）

- **不重开 NFC-approve 的安全签字讨论。** 第 7 步只记录"要做的话技术上该怎么做"，
  批不批准是另一件事、另一次对话。不要因为第 3-4 步把钩子都接通了就顺手把它做了。
- **不假设对方会回应。** 第 1-4 步的产出在 JPeetz 完全不回应、甚至明确拒绝的情况下
  价值不减一分。第 5 步预算半天，无回应即转向，不做任何形式的追问。
- **不往 `NousResearch/hermes-agent` 提核心 PR**（F12），也不改本机
  `~/.hermes/hermes-agent/` 下的任何文件——插件走 `~/.hermes/plugins/` 或独立仓库。
- **不改 Hermes Studio 的鉴权模型。** F8 那套"无密码即放行"是对方的信任模型选择，
  我们只是不把"贴一下 = 授权"建在这一层（第 7 步已说明理由），不去替对方修。
- **不为了刷好感去修对方的 KaTeX 依赖 bug（#11/#14）**，除非对方在第 5 步的 issue 里
  主动提到需要帮手。
- **不把 Hermes 变成 quote0-desk 的硬依赖。** 照 `providers/buddy.py` 的既定纪律：
  没装 Hermes 的使用者（公开仓库里的绝大多数）不受任何影响。
- **不改设备侧架构。** 还是 2 个可用槽（Text + Image），Hermes 卡跟现有 9 张卡一样
  走 `scheduler.py` 分时复用，不申请新槽、不重开 Canvas、不动用户自留的 GENERAL 槽。
- **不把 Studio 的 UI 搬进 quote0-desk 控制台**（cron manager / 审批面板那套）。
  选项 F 是兜底，不是目标；今天刚做完的控制台不在本轮改动范围内。
- **不做多智能体编排的可视化**（crews 活动流之类）——296×152 的屏放不下，
  这是设备物理约束，不是优先级问题。

## 六、完成定义

1. 第 1 步的两个验证点通过，或明确报告"本机跑不起来"并停下——**不接受用 mock 数据
   假装验证过**。
2. 第 2 步的卡在 gateway 开 / 关两种状态下都验证过（降级路径跟启用路径同等重要）。
3. 第 4 步在真机上跑通：一个 `deliver=quote0` 的 cron job 把结果送上了墨水屏，
   且全程没有修改 hermes-agent 或 Hermes Studio 的任何文件。视频/照片已留档。
4. 第 3-4 步的实现遵守了 D1-D4 四条安全设计决策，其中 D1（agent 不能写 `link`）
   要在代码里有显式约束，不能只写在文档里。
5. `docs/DEVICE-FACTS.md` 新增一节，记录本轮的真实结果——包括失败的、否决的、
   降级的（例如第 3 步若退到 tool-only 形态，必须写明"这不是第五个渠道"）。
6. 第 5 步无论结果如何（合并 / 拒绝 / 无回应）都要如实记录，**不允许把"已提 issue"
   当成"已达成合作"来汇报**。
7. 第 6、7 步在本轮结束时应仍处于未执行状态，除非用户在过程中另行明确批准。

---

### Critical Files for Implementation

- `/Users/bruce/dev/quote0-desk/providers/buddy.py` — 外部数据源集成的唯一模板（可选依赖 / 只读 / 永不抛异常 / `available` 契约），`providers/hermes.py` 照抄这套纪律
- `/Users/bruce/dev/quote0-desk/server.py` — `/t/*` NFC 回调路由与 `/api/push` 的落点，第 3 步插件的 send 目标、第 6 步 job 触发路由都加在这里
- `/Users/bruce/.hermes/hermes-agent/plugins/platforms/ntfy/adapter.py` — 593 行的活样板，`register()` 里的 `cron_deliver_env_var` + `standalone_sender_fn` 是「第五个投递渠道」的全部机关
- `/Users/bruce/.hermes/hermes-agent/gateway/platforms/ADDING_A_PLATFORM.md` — 官方明写"第三方走插件路径、零核心改动"的依据，第 3-4 步的规格来源
- `/Users/bruce/dev/quote0-desk/docs/PLAN-next-round.md` — T6 格式基准 + 末尾那条 NFC-approve 候选功能（本规划第 7 步与之衔接，不覆盖它的签字要求）
