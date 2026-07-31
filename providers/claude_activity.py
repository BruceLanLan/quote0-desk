"""Claude Code 活动状态：解析本地 JSONL 转录，不装任何 hook。

token 统计部分移植自 pocket-prophet-dashboard/providers/ccusage.py（同一
台机器上跑的同一套 Claude Code，解析逻辑完全适用，不需要改）。这里额外
加了"最近是否有活跃 session"的判断——用"最近一个转录文件的 mtime 是否在
一个短窗口内"当代理指标，因为装 hook 才能拿到真正的 session 生命周期
事件，而状态灯只是"看一眼"，没必要为了这张卡去碰 Claude Code 的 hooks
配置（那是全局设置，跟这个项目的范围不对等）。
"""
import glob
import json
import os
from datetime import datetime, timedelta, timezone

ACTIVE_WINDOW_SECONDS = 180  # 转录文件在这个窗口内被写过，就认为"活跃中"

# token 统计逻辑与 pocket-prophet-dashboard/providers/ccusage.py 一致
PRICING = {
    "opus": {"input": 15.0, "output": 75.0, "cache_write": 18.75, "cache_read": 1.5},
    "sonnet": {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.3},
    "haiku": {"input": 0.8, "output": 4.0, "cache_write": 1.0, "cache_read": 0.08},
}
DEFAULT_PRICING = PRICING["sonnet"]


def _config_dir() -> str:
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def _pricing_for(model: str) -> dict:
    model_l = (model or "").lower()
    for key, p in PRICING.items():
        if key in model_l:
            return p
    return DEFAULT_PRICING


def _parse_ts(ts_str):
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None


def _project_name_from_file(path: str) -> str:
    """转录文件目录名是把完整路径的 `/` 换成 `-` 拼出来的（比如
    `/Users/you/dev/quote0-desk` 会变成 `-Users-you-dev-quote0-desk`），
    项目名本身如果带连字符（`quote0-desk`）就没法从这个字符串可靠切分回来。

    转录文件每一行其实都带 `cwd` 字段，是真实路径，取 basename 才准——
    只取 basename 不取完整路径，也顺便避免在屏幕上露出用户名之类的本机
    路径片段。"""
    try:
        with open(path, "rb") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cwd = d.get("cwd")
                if cwd:
                    return os.path.basename(cwd.rstrip("/")) or "未知项目"
    except OSError:
        pass
    return "未知项目"


def scan() -> dict:
    """返回今日 token 统计 + 最近活跃项目 + 是否活跃中。"""
    pattern = os.path.join(_config_dir(), "projects", "**", "*.jsonl")
    paths = glob.glob(pattern, recursive=True)

    now_ts = datetime.now(timezone.utc)
    today_start = now_ts.astimezone().replace(hour=0, minute=0, second=0, microsecond=0)

    today_tokens = 0
    cost = 0.0
    latest_mtime = 0.0
    latest_path = None

    for path in paths:
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if mtime > latest_mtime:
            latest_mtime = mtime
            latest_path = path

        # 今日 token/成本：只需要扫最近改过的文件，忽略太旧的（性能考虑，
        # 跟 ccusage.py 的增量缓存不同，这里只要"今天"这一个粗粒度统计，
        # 换成每次全量扫也能接受，状态灯不需要那么精确的增量缓存机制）。
        try:
            file_mtime_dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
        except (OSError, OverflowError):
            continue
        if file_mtime_dt < today_start.astimezone(timezone.utc) - timedelta(hours=6):
            continue  # 明显是很久以前就没动过的文件，跳过不解析，省时间

        try:
            with open(path, "rb") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = d.get("message")
                    if not isinstance(msg, dict):
                        continue
                    usage = msg.get("usage")
                    if not usage:
                        continue
                    ts = _parse_ts(d.get("timestamp"))
                    if ts is None or ts.astimezone() < today_start:
                        continue
                    tok = sum(usage.get(k, 0) or 0 for k in (
                        "input_tokens", "output_tokens",
                        "cache_creation_input_tokens", "cache_read_input_tokens",
                    ))
                    if tok == 0:
                        continue
                    today_tokens += tok
                    p = _pricing_for(msg.get("model", ""))
                    cost += (
                        (usage.get("input_tokens", 0) or 0) / 1e6 * p["input"]
                        + (usage.get("output_tokens", 0) or 0) / 1e6 * p["output"]
                        + (usage.get("cache_creation_input_tokens", 0) or 0) / 1e6 * p["cache_write"]
                        + (usage.get("cache_read_input_tokens", 0) or 0) / 1e6 * p["cache_read"]
                    )
        except OSError:
            continue

    active = bool(latest_mtime) and (now_ts.timestamp() - latest_mtime) < ACTIVE_WINDOW_SECONDS
    project = _project_name_from_file(latest_path) if latest_path else None

    return {
        "active": active,
        "project": project,
        "today_tokens": today_tokens,
        "estimated_cost_usd": round(cost, 2),
        "last_activity_ts": latest_mtime,
    }
