"""实盘信标：只读 lighter-scalper / stock-radar 已经在写的本地状态文件，
不 import 它们的代码、不触发任何交易逻辑（那两个项目有自己的进程和风控，
这张卡只是"看一眼"，不是"参与"）。

- lighter-scalper：`data/positions.json`（PositionStore 的原子持久化，见
  该仓库 `lighter_scalper/ops/position_store.py`）+ `logs/*.log` 最新
  mtime 当"策略是否还在跑"的粗略信号
- stock-radar：`scripts/.scan_state/*.json`（每个 symbol 一份历史信号
  时间线），取全部 symbol 里时间戳最新的一条当"最新信号"

两边数据都可能是空的/陈旧的——如实显示"当前无持仓"/"策略未运行"，
不编造活跃假象。绝不读取任何带 key/secret/credential 字样的文件。
"""
from __future__ import annotations

import glob
import json
import os
import time

LIGHTER_SCALPER_DIR = "/Users/bruce/lighter-scalper"
STOCK_RADAR_DIR = "/Users/bruce/dev/stock-radar"

STALE_AFTER_HOURS = 24  # 超过这个时长没新日志，就不算"运行中"


def lighter_status() -> dict:
    positions_path = os.path.join(LIGHTER_SCALPER_DIR, "data", "positions.json")
    positions = []
    if os.path.exists(positions_path):
        try:
            with open(positions_path) as f:
                positions = json.load(f)
        except (json.JSONDecodeError, OSError):
            positions = []

    log_pattern = os.path.join(LIGHTER_SCALPER_DIR, "logs", "*.log")
    latest_mtime = 0.0
    for path in glob.glob(log_pattern):
        try:
            latest_mtime = max(latest_mtime, os.path.getmtime(path))
        except OSError:
            continue

    running = bool(latest_mtime) and (time.time() - latest_mtime) < STALE_AFTER_HOURS * 3600
    return {"positions": positions, "running": running, "last_log_at": latest_mtime}


def stock_radar_latest_signal() -> dict | None:
    pattern = os.path.join(STOCK_RADAR_DIR, "scripts", ".scan_state", "*.json")
    best = None
    for path in glob.glob(pattern):
        symbol = os.path.basename(path).replace(".json", "")
        try:
            with open(path) as f:
                entries = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        for entry in entries:
            parts = entry.split("|")
            if len(parts) != 4:
                continue
            _, pattern_name, ts, price = parts
            if best is None or ts > best["ts"]:
                best = {"symbol": symbol, "pattern": pattern_name, "ts": ts, "price": price}
    return best


def fetch() -> dict:
    return {"lighter": lighter_status(), "stock_radar": stock_radar_latest_signal()}
