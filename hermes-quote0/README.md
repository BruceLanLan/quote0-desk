# hermes-quote0

[Hermes Agent](https://github.com/NousResearch/hermes-agent) 的平台插件，把 agent 消息 / cron job 结果送到这个仓库管理的 Quote/0 墨水屏上——插件本身不直接持有 Dot 云端 API 凭据，实际推送经由主项目已经在跑的 `server.py`（见 [`../providers/hermes_inbox.py`](../providers/hermes_inbox.py) + [`../cards/hermes_inbox.py`](../cards/hermes_inbox.py)）。

outbound-only：Quote/0 没有聊天界面，这个适配器不接收 inbound 消息，也不维护长连接。所有内容都会在屏幕上带 `Hermes Agent` 签名，且这个适配器永远不会自己指定 NFC 回调链接——链接由 quote0-desk 的卡片层固定生成或留空，不给 prompt injection 留任何把物理贴一下变成钓鱼入口的机会。

## 安装

```bash
git clone https://github.com/BruceLanLan/quote0-desk.git
mkdir -p ~/.hermes/plugins
cp -r quote0-desk/hermes-quote0 ~/.hermes/plugins/hermes-quote0
hermes plugins enable quote0-platform
```

## 配置

在 `~/.hermes/.env` 里加：

```bash
QUOTE0_ENABLED=true
# QUOTE0_DESK_URL=http://127.0.0.1:5252   # 可选，默认就是这个
# QUOTE0_HOME_CHANNEL=quote0              # 可选，非空即可，开启 cron deliver=quote0
```

前提：quote0-desk 服务本身要在跑（`python3 server.py`，或装了它的 launchd 常驻服务），且已经用官方 Dot App「内容工坊」建好一个文本 API 内容槽——这个插件不会替你建，它只是往 quote0-desk 已经在管理的槽里推内容。

## 用法

配好之后，agent 可以像发消息到 Telegram/Discord 一样发到 quote0：

```
send_message(platform="quote0", content="今天的进度：...")
```

或者建一个 cron job，定期把结果送上屏幕：

```bash
hermes cron create "0 9 * * *" --deliver quote0 --no-agent --script my_report.sh
```

## 这个插件不做什么

- 不接收 Quote/0 的任何输入——NFC 贴一下走的是 quote0-desk 自己的 `/t/*` 路由，跟这个插件无关。
- 不让 agent 指定 NFC 回调链接（安全设计，见上）。
- 不做审批（`send_exec_approval`）——技术上可行（`BasePlatformAdapter` 有这个钩子），但"贴一下 NFC = 授权一次工具调用"是一个独立的安全签字问题，这个插件目前的范围里没有实现。

## 验证过什么

`send()` 路径（含 cron 投递用的 `standalone_sender_fn`）已经在真实运行的 hermes-agent gateway 上验证：插件正确注册为 `quote0` platform，`GET /health/detailed` 显示 `connected`；一个真实的 `deliver=quote0` cron job 端到端把结果送上了墨水屏，屏幕内容带固定的 `Hermes Agent` 签名、NFC 链接固定为空。

目前是 quote0-desk 项目里一个可用但独立的组件，没有主动往 [Hermes Studio](https://github.com/JPeetz/Hermes-Studio) 提过整合。注意这里的安装方式是手动复制这个子目录，不是 `hermes plugins install <owner>/<repo>` 那种一键装——那条命令期望插件在仓库根目录，没有验证过它对"插件是仓库里某个子目录"这种情况的支持。
