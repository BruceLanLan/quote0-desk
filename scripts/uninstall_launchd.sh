#!/bin/bash
# 卸载 install_launchd.sh 装的两个 LaunchAgent，停止开机自启。
set -euo pipefail
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
UID_NUM=$(id -u)

for label in com.quote0desk.server com.quote0desk.tunnel; do
  launchctl bootout "gui/$UID_NUM/$label" 2>/dev/null || true
  rm -f "$LAUNCH_AGENTS_DIR/$label.plist"
  echo "已卸载 $label"
done
