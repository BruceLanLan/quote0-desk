# Quote/0 真机事实基准（M0）

本文件是后续所有开发的事实依据。每条标注确认方式；未验证的显式写「未验证」，
不用推测填充。设备：`series=quote / model=quote_0 / edition=2`，固件 `2.0.8`。

## 已确认

### 槽模型：API 只更新预先在 App 里创建好的内容槽，不能凭空创建（P4，2026-07-31 实测）

两次独立探测（text 隐含在 P1、canvas 在 P4）返回完全一致的诊断，官方原话：

> "API 密钥已通过校验，但设备 <DEVICE_SERIAL> 循环任务中未找到**文本 API 内容**，
> 请前往 Dot. App **内容工坊**中添加文本 API 内容到设备循环任务中。如果您已经
> 添加，请删除后重新添加。"

> "API 密钥已通过校验，但设备 <DEVICE_SERIAL> 循环任务中未找到**画板 API 内容**，
> 请前往 Dot. App 内容工坊中添加画板 API 内容到设备循环任务中。"

**结论：** 编排架构必须是「N 个内容槽（在 App 里手动建好）被我这边的服务轮流
更新内容」，不是「我这边随便创建新内容项」。这决定了 M4 阶段的 scheduler 形态——
不是设备自己在一堆独立内容间轮播，是**我往同一个槽（或几个槽）里换内容**。

**对用户的行动项：** 需要在 Dot App「内容工坊」里，把 **文本 API 内容**和
**画板 API 内容**（以及后续要用的 图片 API 内容）添加到设备的循环任务里。
添加后不需要告诉我具体 key——`GET /loop/list` 会自动列出来，代码里按
`type` 字段（`TEXT_API` / `IMAGE_API` / `CANVAS_API`）识别，不需要手填。

### 设备基本状态（GET /status，2026-07-31）

```
version: 2.0.8
current: 电源活跃中（已接电源）
wifi: -44 dBm
renderInfo.last: 2026年7月31日 00:34（本次探测前）
renderInfo.next: battery +3min / power +1min
```

### 设置（GET /settings）

```
timezone: Asia/Shanghai
interval.powerMs: 60000
interval.batteryMs: 180000
sleep: enabled, 02:00–09:00
```

### 循环任务当前内容（GET /loop/list，探测前）

两项，均 `type=GENERAL`（App 自带的和风天气内容，非 API 内容）：
`key=5fq8SKUbjmyF`（带地理位置：海南省海口市龙华区）、`key=XRwojqBRrJmf`。

`GET /fixed/list` 为空。

## P1：text `refreshNow` 延迟（已确认，2026-07-31）

从 `POST /text` 返回到 `GET /status` 检测到 `renderInfo` 变化，实测 **≈4.7 秒**
（POST 本身耗时 1.7s + 轮询间隔）。足够快，NFC 交互体验不用担心这段延迟。

## P4：槽模型（已确认，见上方）+ 一个衍生重要发现——自主轮转

**设备会按 `interval.powerMs`（通电时 60 秒）自主轮转 loop 里的全部槽位**，
不是「只显示我最后推送的那个」。连续 4 次 `GET /status`（间隔 2 秒）观察到：
前 3 次 `current.image` 是我们推的 TEXT_API 内容，第 4 次（约 60s 后）自动跳到
了 loop 里另一个 `GENERAL` 槽（第三方天气插件 techflow）——**期间我们没有做任何
推送**，纯粹是设备自己按计划往前走了一格。

**结论对架构的影响：**
- `refreshNow: true` 只保证"推送后立刻切到这张卡"，**不保证它会一直显示**——
  过了 `interval.powerMs` 这个周期设备会自己转到 loop 里的下一项，可能是我们
  的另一张卡，也可能是 App 里配置的第三方内容（天气插件等）。
- 如果想让某张卡"一直挂着"直到我们主动换，两个方向待验证：a) 把
  `interval.powerMs` 调到很大（合法上限 12 小时），完全靠我们自己 `/next` 或
  重新 push 来推进；b) 接受轮转，把它当"背景节奏"设计（类似电台切歌），
  卡片设计上都做成"当下瞬间值得看"而不依赖长期驻留。**这是 M4 排期前要定的
  架构决策，不是可以往后拖的细节。**
- **`renderInfo.current.image` 的可靠性需要修正**：它准确反映"这一刻设备正在
  显示什么"，但**不等价于"我最近一次推送的内容"**——中间可能被自主轮转覆盖掉了。
  开发期用它核对渲染效果时，必须在推送后的几秒内立刻查询，不能拖。

### 疑似 loop 槽位数量上限为 3（2026-08-01 新证据，仍未 100% 确认）

之前记录过一次"加 TEXT_API/CANVAS_API 后一个 GENERAL 天气槽消失"，当时不
确定是槽位上限还是巧合。今天加了 IMAGE_API 槽（用户在内容工坊操作）之后，
`GET /loop/list` 显示只剩 3 项：`IMAGE_API` + `TEXT_API` + 1 个 `GENERAL`，
**`CANVAS_API` 槽整个消失了**——推 `status` 卡直接收到跟"槽不存在"一模一样
的 404："循环任务中未找到画板 API 内容"。`GET /fixed/list` 为空，不是转移
到了 fixed 列表。

两次独立观察都是"加一个新槽，另一个槽被顶掉，总数维持在 3"，指向**账号/
设备的 loop 槽位可能存在上限（大概率是 3）**，不是我们代码或推送逻辑的
问题——`push_card("status")` 走的还是原来验证过的 Canvas API 路径。

**对架构的影响：** proverb/status/todo/capsule/beacon 这 5 张 Canvas 卡
现在推不上去，直到内容工坊里重新腾出一个槽给 Canvas API（可能要去掉那个
`GENERAL` 天气槽，或者上限本身有办法调，需要用户去 App 里确认）。这不是
"待验证细节"，是当前会阻塞 5 张卡的真实事实，排优先级应该在两张一起处理。

## P5：296×152 横屏中文可读字号下限（已确认，2026-07-31）

自己读图（`scripts/_m0_shots/p5_size*.png`）判断：**12px 清晰可读，10px 明显
发糊、笔画挤连**。下限定为 **12px**（Canvas `text-12-chillduansans`）。
对照上个项目 200×200 屏是 13px 下限——横屏更宽但物理像素密度相近，结论接近。

## 架构决策：loop 槽位硬上限 3 个，账号只留 2 个给我们（2026-08-01 定稿，替换 07-31 的旧结论）

**这一节是重写，不是补充**——07-31 当时以为"申请更多 Canvas 槽位"只是
没去做，08-01 拿到了反证：加 IMAGE_API 槽之后 CANVAS_API 槽直接消失，
`loop/list` 数量稳定卡在 3。用户确认了背后的账号配置：**设备 loop 槽位
上限就是 3 个**，其中 1 个被用户自己留的官方"新闻"内容占着（用户主动
决定保留，不是我们能碰的），所以**我们实际能用的只有 2 个槽：Text API +
Image API，Canvas API 从架构里出局，不是"以后申请回来"的待办**。

**验证过 Text API 能接住原来 5 张 Canvas 卡吗？** 能。`docs/DEVICE-FACTS.md`
这条本身就是证据：Text API 原生支持 `\n` 换行（不需要 Canvas 那个
`whiteSpace: pre-line` hack），长文本会自动折行不截断，默认排版
（标题加粗大字 + 正文 + 右下角签名）不需要手调字号也清晰可读——08-01
把 proverb/status/todo/capsule/beacon 五张卡实测推过一遍，`renderInfo.
current.image` 逐张核对，全部合格（唯一观感瑕疵：status 卡的美元数字
有时会折行折在数字中间，能读但不好看，未处理，不是功能问题）。

**结论：** `canvas/template.py` 只留 `simple_data()`（产出 title/message/
footer 三段），`simple_card()`（Canvas 的 windowData/Tailwind 构建器）
已删除。`push.py` 的路由变成两路——卡返回 `png` 走 Image API，否则走
Text API——不再有 Canvas 分支。**9 张卡共享 2 个槽**（不是共时性展示，
是 `scheduler.py`（M6）分时复用，这条判断没变，变的只是"共享几个槽"）。

**扩展的问题不是"槽位不够"，是"同时刻只能露出几张脸"**：槽位数量限制
的是同时能挂几种卡，不限制卡的总数——加第 10/11 张卡不花任何槽位成本，
调度器照样轮。真正因这个上限而值得讨论的设计选择是：`interval.powerMs`
现在调到 12 小时上限是为了防止设备自转打断我们手动控制的节奏；但既然
现在文字槽和图片槽是两种不同类型，理论上也可以反过来利用设备原生轮转
（把 `powerMs` 调回适中值，让设备自己在"当前文字卡"和"当前图片卡"之间
交替显示）——**已判断否决，不采用**：`loop/list` 现在是 3 项（文字槽、
图片槽、用户自留的新闻槽），一旦开原生轮转，设备是三项一起轮，不是只在
我们两个槽间切换；这个"无聊计时器"不管我们刚推过什么内容，到点就跳到
下一项，会直接打断 NFC 交互"贴一下之后结果要稳稳停在屏幕上"这个核心
体验（宠物摸一下、签筒抽一签之后，几十秒内被自动跳去新闻，交互的即时
反馈感就废了）。结论：继续维持 `powerMs` 拉满 12 小时、完全靠
`scheduler.py` 手动控制节奏，这不是审美取舍，是有具体技术后果的选择。

## Canvas 里 `\n` 不会自动换行，必须显式 `whiteSpace: pre-line`（已确认，2026-07-31）

用官方文档里 `message` 字段常见的 `\n` 写法（TEXT_API 支持 `\n`，但 Canvas 是
不同的渲染管线）推了一段带 `\n` 的多行文案，实测**整段被拼成一行**，`\n`
被当空白吃掉了。加上 `props.style.whiteSpace: "pre-line"` 后 `\n` 才真正生效
换行——已经修进 `canvas/template.py` 的 `simple_card()`，所有走这个模板的卡
自动带上，不需要每张卡各自处理。

### P6：Image API 槽已加，四张图片卡全部真机验证通过（2026-07-31）

用户在 Dot App 内容工坊加好「图片 API 内容」槽后，`cli.py push pet/liuyao/qimen`
三条命令依次实测，`renderInfo.current.image` 下载下来逐张肉眼核对：宠物 ASCII
造型对齐正常、六爻爻线清晰、奇门九宫格文字不糊。签筒（`qiantong`）复用
liuyao/qimen 的 `build()`，不用单独测。

灰阶细节：至少能正常显示纯黑文字/线条在白底上，抖动轻微不影响辨识；
是否支持中间灰阶未特意测（几张卡设计上都没依赖灰阶，用不上这个信息也不影响开发）。

## 待验证

- P2：NFC 贴一下打开的是否是当前显示内容的 `link`（**项目立足点，最高优先级**，需用户配合真机贴一下）
- P3：`link` 支持哪些 scheme（局域网 http / 公网 https / `shortcuts://`，需用户配合）

## 隐私审查记录（M6，2026-07-31）

`git grep` 对照仓库根目录（`/Users/bruce/dev/quote0-desk`，确认不是误扫到
`~` 那个大仓库）跑了一遍：

- API Key（`dot_web_`/`dot_app_` 前缀）：未出现在任何跟踪文件里，本来就只经环境变量。
- 设备序列号：本文档、`scripts/m0_probe.py` 里的实际序列号已替换成占位符
  `<DEVICE_SERIAL>` / `<你的设备序列号>`。
- 用户名路径：`providers/beacon.py`、`capsule.py`、`pet.py` 里硬编码的
  `/Users/bruce/...` 已改成 `os.path.expanduser("~/...")`，不再落死用户名。
- 新增 `providers/claude_quota.py`（2026-08-01）引入了另一类凭据——Claude
  Code 自己的 OAuth accessToken（读 `~/.claude/.credentials.json`，只读
  不回写）。这个 token 不经过 config.json，也不打印/不落日志，`git grep`
  加了 `sk-ant-oat` 前缀和 `accessToken"\s*:\s*"...` 字面量两个新 pattern，
  确认干净。

`scripts/_m0_shots/` 下的截图和文件名本身都不含序列号，CDN 渲染 URL
（含序列号路径段）没有被写进任何跟踪文件，`git grep` 确认为空。
