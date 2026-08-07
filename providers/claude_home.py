"""Claude Code 配置目录发现：一台机器可能同时装了多个 profile（比如
`~/.claude` 默认、`~/.claude-opus` 另开的 Opus 品牌配置各跑各的会话）。
`claude_activity.py`/`claude_quota.py` 原来硬编码只认 `~/.claude`，在这种
机器上会扫到一个当下没有活动的目录——状态灯显示"今日 0 tokens"，不是真的
没数据，是找错了地方（本机实测过：真实活跃会话在 `~/.claude-opus`，
`~/.claude/projects` 里全是几个月前的旧文件）。
"""
from __future__ import annotations

import glob
import os


def candidate_dirs() -> list[str]:
    """按优先级返回可能的 Claude Code 配置目录。`CLAUDE_CONFIG_DIR` 显式
    设了就只认它，跟官方 CLI 行为一致——用户既然设了这个环境变量，就是在
    明确指定"用这一个"，不该被我们的多目录猜测覆盖。没设的话枚举
    `~/.claude*` 里"看起来像"配置目录的那些（有 `projects/` 子目录或
    `.credentials.json`），`~/.claude` 排最前（最常见的默认值，多数机器
    只有这一个，函数对这种情况原样返回单元素列表，行为不变）。
    """
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        return [os.path.expanduser(env)]

    home = os.path.expanduser("~")
    found = []
    default = os.path.join(home, ".claude")
    if os.path.isdir(default):
        found.append(default)
    for path in sorted(glob.glob(os.path.join(home, ".claude-*"))):
        if path in found or not os.path.isdir(path):
            continue
        looks_like_config = (
            os.path.isdir(os.path.join(path, "projects"))
            or os.path.exists(os.path.join(path, ".credentials.json"))
        )
        if looks_like_config:
            found.append(path)
    return found or [default]
