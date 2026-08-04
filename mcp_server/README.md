# quote0-desk MCP server

把具体的内容卡暴露成 Claude 能直接调用的工具（摇一卦、摸摸宠物、设今日任务……），不是又一个通用文本/图片透传——那个方向 MindReset 生态里已经有至少 4 个独立实现（`stvlynn/quote0-mcp`、`thomaszdxsn/quote0-mcp`、`Lakphy/mindreset-dot-mcp`、`Ebispongebob/dot-agent-mcp`），重复没有意义。这里的差异化是"工具即卡片"：调用 `draw_hexagram()` 直接摇一卦推上屏，不用先构造文本/图片再自己拼推送参数。

## 为什么是独立的 Python 环境

`mcp` SDK 要求 Python 3.10+，quote0-desk 主项目为了兼容这台机器已经装好的依赖，一直走系统自带的 Python 3.9。与其互相迁就版本，这个 MCP server 干脆是**主项目的一个 HTTP 客户端**——通过 `server.py` 已经在跑的 `/api/*` 接口调用卡片，不直接 import 卡片/provider 代码，两边的 Python 版本互不影响。

## 安装

```bash
cd mcp_server
python3.12 -m venv .venv   # 任何 >= 3.10 的解释器都行；系统自带的 python3 通常是 3.9，装不了，得用 brew 的 python@3.11/3.12/3.13
.venv/bin/pip install -r requirements.txt
```

## 前提：quote0-desk 主服务得在跑

```bash
cd ..
python3 server.py   # 或者已经按 README 装了 launchd 常驻服务
```

默认连 `http://localhost:5252`，换地址用 `QUOTE0_DESK_URL` 环境变量覆盖。

## 接入 Claude Code / Claude Desktop

在 MCP 配置里加一项（`command` 和 `args` 填绝对路径，两边替换成实际的仓库位置）：

```json
{
  "mcpServers": {
    "quote0-desk": {
      "command": "/绝对路径/quote0-desk/mcp_server/.venv/bin/python",
      "args": ["/绝对路径/quote0-desk/mcp_server/server.py"]
    }
  }
}
```

## 工具列表

| 工具 | 效果 |
|---|---|
| `push_pet()` | 推屏上宠物卡 |
| `pat_pet()` | 摸摸宠物，触发一次性开心反应 |
| `draw_hexagram()` | 摇一卦（六爻） |
| `cast_qimen()` | 按当前时间起一盘奇门遁甲 |
| `draw_qiantong()` | 抽签筒（摇卦/奇门二选一，真随机） |
| `push_daily()` | 推日课卡（当前四柱干支） |
| `push_proverb()` | 推桌面箴言机卡 |
| `push_status()` | 推 Claude Code 状态灯卡 |
| `set_today_task(task)` | 设置今日一件事并推送 |
| `toggle_today_task()` | 切换今日任务完成状态 |
| `get_device_status()` | 只读查看设备在线状态 |
| `list_cards()` | 列出全部内容卡 |

真机验证过：`draw_hexagram`/`push_daily`/`set_today_task`/`toggle_today_task` 都推过真实设备并截图核对过内容一致；quote0-desk 主服务未启动时，工具会返回明确的"连不上 quote0-desk"提示，不是裸的连接异常堆栈。
