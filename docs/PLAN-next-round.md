# quote0-desk 下一轮工作规划（T6 规划交接单，2026-08-04，Opus 5 规划）

## 进度更新（2026-08-04，同一天内完成）

- **第 4 步（仓库公开）已执行**——用户明确说"开放github吧"，不再是"想
  公开"的意图表述，是直接指令，`gh repo edit --visibility public` 已跑，
  `docs/img/` 的截图和 README 在 GitHub 上渲染正常，已核实。
- **新增一项计划外的工作**：发现用户本机另有一个 `~/buddy-bridge` 项目
  （hook 桥接守护进程，真实的 Claude Code 活动信号源），已接入
  `providers/pet.py`（sleep/idle/busy/attention 状态判定）和
  `cards/status.py`（活跃指示），可选
  增强、真机验证过、graceful degradation 到位。详见对应 commit。
- 第 1 步（P3 `shortcuts://`）、第 3 步（日课卡）、第 5 步（MCP）、
  第 6 步（showcase 提交）**仍未做**，见下方原始步骤。

## 目标

在项目当前状态（M0-M6 完成，NFC 闭环真机验证通过，仓库仍私有）之上，
把它从"能跑但只在这台机器不重启的前提下能跑"推进到"日常真的能用、
可以公开发布"，同时补完计划内唯一没做的卡和唯一没测的 NFC scheme。

## 背景事实（自包含，不需要翻对话）

- Quote/0 账号 loop 槽位硬上限 3 个，1 个被用户自留的官方内容占着，
  实际可用 2 个：Text API + Image API。Canvas API 已彻底出局。
  详见 `docs/DEVICE-FACTS.md`「架构决策」一节。
- NFC 反馈闭环（贴一下 → 服务器动作 → 屏幕刷新）已真机验证通过
  （`docs/DEVICE-FACTS.md` P2 + M2 两节）。已知唯一故障模式：手机自己
  开着 VPN 会导致 NFC 跳到 Dot App 内部预览而不是转发到我们的网页。
- `config.nfc_base_url()` 是当前 NFC 链接的唯一来源，各卡自己拼
  `{base}/t/...`。**这个值现在指向一个 `cloudflared` 临时隧道
  （`trycloudflare.com`），进程一停地址就失效**——这是目前项目"能长期
  可用"最大的单点故障，不是某张卡的问题，是整条 NFC 链路的地基。
- Git 历史已用 `git filter-repo` 清洗过（设备序列号、局域网 IP、主机名
  全部替换成占位符）并 force-push，仓库当前**仍是私有**——用户表达过
  "想公开"的意图，但没有明确指令"现在就切换"，这条不能替他们做主。
- README 已经过一轮面向公开发布的重写（图、License、排障、槽位说明
  前置），LICENSE（MIT）已加。
- `providers/qimen_engine.py` 已经有干支排盘引擎（移植自
  pocket-prophet-dashboard），日课/时辰盘卡缺的是"包一层 provider +
  card"，不缺底层算法。
- MCP 生态里已有至少 4 个独立实现（`stvlynn/quote0-mcp` 36 星最大，
  `thomaszdxsn/quote0-mcp`、`Lakphy/mindreset-dot-mcp`、
  `Ebispongebob/dot-agent-mcp`），全部是通用文本/图片透传，没有一个
  暴露"具体卡片"当工具。

## 约束

- 不动用户自留的官方新闻 GENERAL 内容槽。
- API Key/设备序列号/局域网信息一律走环境变量或占位符，不落库——延续
  已经建立的纪律，新加的 provider/card 照样适用。
- 仓库公开与否是用户决定，代码/文档可以做到"随时能公开"，但不能替他们
  按下这个按钮。
- 不新增需要用户长期维护账号/订阅的外部依赖（例如需要注册付费的隧道
  服务）除非明确必要且提前说明。

## 步骤（按风险与信息增益排序，最不确定的在前）

1. **P3：测 `shortcuts://` scheme。**
   推一张卡，`link` 设成 `shortcuts://run-shortcut?name=<某个用户已有的
   快捷指令名>`，贴一次。
   → 验证点：用户报告 iOS 快捷指令是否被拉起。
   → 若失败：记录进 `docs/DEVICE-FACTS.md`「待验证」，不阻塞后续步骤——
   这条只是"锦上添花"的可能性探测，不是地基。
   成本最低（一次贴的动作），信息增益直接决定"能不能做触发 iOS
   自动化"这个功能方向，排第一。

2. **NFC 隧道的长期方案——当前项目最大的单点故障。**
   两个选项二选一，跟用户确认后再动手：
   - a) 注册一个 Cloudflare 账号，建named tunnel（固定域名，不随进程
     重启失效）；
   - b) 写一个 launchd plist，让 Mac 开机自动拉起
     `cloudflared tunnel --url http://localhost:5252`，脚本解析新地址
     写回 `config.json` 的 `nfc_base_url`。
   → 验证点：重启这台 Mac，不做任何手动操作，贴一张卡的 NFC，屏幕正常
   刷新。
   → 若失败：回退到"每次开机手动跑 cloudflared + 手动更新配置"，至少
   写清楚这个手动步骤，不能什么都不做。
   这一步不做，后面加的所有卡/功能在重启后全部啞火，优先级实际上
   高于新功能开发。

3. **日课/时辰盘卡。**
   `providers/daily.py`（新建，复用 `qimen_engine.py` 的干支排盘部分）
   + `cards/daily.py`（Text API，参照 `cards/status.py` 的结构）。
   → 验证点：`python3 cli.py push daily` + `cli.py snapshot` 核对当前
   时辰的干支显示正确（对照万年历或 `qimen_engine.py` 里已验证过的
   排盘逻辑手工核算一次）。
   计划里唯一没实现的卡，逻辑现成，风险低，放在隧道问题解决之后是因为
   "新卡能推上去"依赖"NFC 链路长期可用"这个前提已经成立，不是这张卡
   本身有风险。

4. **决定要不要把仓库切成公开。**
   前三步做完、README 和 DEVICE-FACTS.md 都是"经得起陌生人看"的状态后，
   跟用户确认一次"现在公开吗"，不要替他们决定。
   → 验证点：`gh repo edit BruceLanLan/quote0-desk --visibility public`
   执行后 `gh repo view --json visibility` 返回 `PUBLIC`；再拉一次
   README 的渲染页面，确认 4 张截图正常显示（相对路径在 GitHub 上通常
   没问题，但这是"每个访客都会看到的门面"，值得实际确认而不是假设）。

5. **MCP wrapper（仅在 1-4 完成后考虑）。**
   差异化点是暴露具体卡片当工具（`push_pet`、`draw_qiantong`、
   `set_todo` 这类），不是再做一个通用文本/图片透传——那个方向已经有
   4 个实现在做了，重复没有意义。
   → 验证点：从一个新的 Claude Code 会话里，调用某个卡片工具，观察
   Quote/0 屏幕真的变化。
   这一步是"锦上添花"的扩展功能，不是把项目从能用推到好用的必经之路，
   放在最后。

6. **提交官方 co_create showcase（`/submit#idea`）。**
   仅在第 4 步完成（仓库已公开）且第 2 步的隧道问题有稳定方案之后——
   提交一个"贴了 NFC 会打不开"的项目给官方展示，观感上不划算。
   → 验证点：官方页面出现这个项目的条目。

## 范围边界（这次明确不做的事）

- 不重新讨论"要不要用原生设备轮转代替 scheduler.py"——已经在
  `docs/DEVICE-FACTS.md` 里定稿否决过，理由没变，不重开。
- 不追加"测试跑挂 = 宠物不高兴"这类需要在其他项目装 hook 的联动功能——
  `providers/pet.py` 的文档里已经明确写了这超出这张卡的范围。
- 不迁移到 Canvas API——账号槽位上限已经把这条路堵死，不是"以后申请
  回来"的待办。
- 不在这一轮里处理 09-02:00 的设备休眠窗口对推送/NFC 的影响——现有
  代码没针对这个窗口做特殊处理，属于已知但优先级较低的边界情况，不在
  这次范围内主动测试。

## 完成定义

六步全部验证点通过；宣布完成前，`docs/DEVICE-FACTS.md` 要新增对应
章节记录每一步的真实结果（包括失败/否决的），不能只在对话里口头汇报。
第 4 步（仓库公开）执行前必须有用户的明确确认，不能因为前面几步做完了
就默认这一步也批准了。（**2026-08-04 更新**：第 4 步已在用户明确指令
下执行，见上方进度更新。）

## 候选功能——需要用户明确批准才能动手，不能顺手做

**"waiting → NFC 批准"**：buddy-bridge 的协议里有 `permission` 命令
（`decision: "once"/"deny"/"always"`）。构想是：`snapshot.waiting > 0`
时推一张卡显示"待批准：Bash — rm -rf /tmp/foo"，`link` 指向一个新路由
`/t/approve`，贴一下 NFC 就相当于在电脑上点了"允许"。

这是目前想到的、最能体现"NFC 真的是交互不是摆设"的功能——别的项目都是
面板，这个会是"物理动作批准一次代码执行"。但**这不是一张普通内容卡**：
贴一下会真的授权一次工具调用，做错了后果是真实的（比如批准了一个本不该
批准的删除命令）。真要做，至少要：
- 明确排除高风险工具（`rm`/`git push --force`/任何写权限操作）不走这条
  NFC 快捷路径，只保留只读或低风险操作能被这样批准；
- 在 README 里写清楚这条路径的权限含义，不能让使用者以为这只是"看一眼"。

不在这一轮的六步里，因为这是一个需要用户对着安全含义点头的决定，不是
"做就完了"的功能开发。下次讨论时提这一条。
