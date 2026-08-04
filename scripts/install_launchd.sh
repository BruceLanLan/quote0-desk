#!/bin/bash
# 把 server.py + cloudflared 隧道注册成两个 launchd LaunchAgent，开机/登录
# 自动拉起，进程死了也自动重启（KeepAlive）。之前这两个都是手动在终端里
# 跑，会话一断或者 Mac 一重启就没了——这是 docs/PLAN-next-round.md 里
# "NFC 隧道最大单点故障"那一条的解法（选项 b：不用注册 Cloudflare 账号，
# 代价是隧道地址每次重启会变，但 tunnel_daemon.sh 会自动把新地址写回
# config.json，不需要人工干预）。
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
UID_NUM=$(id -u)

mkdir -p "$LAUNCH_AGENTS_DIR" "$REPO_DIR/data"
chmod +x "$REPO_DIR/scripts/run_server.sh" "$REPO_DIR/scripts/tunnel_daemon.sh"

render_plist() {
  local label="$1" program="$2" out="$3"
  sed -e "s#{{REPO_DIR}}#$REPO_DIR#g" \
      -e "s#{{LABEL}}#$label#g" \
      -e "s#{{PROGRAM}}#$program#g" \
      "$REPO_DIR/scripts/launchd/template.plist" > "$out"
}

render_plist "com.quote0desk.server" "$REPO_DIR/scripts/run_server.sh" \
  "$LAUNCH_AGENTS_DIR/com.quote0desk.server.plist"
render_plist "com.quote0desk.tunnel" "$REPO_DIR/scripts/tunnel_daemon.sh" \
  "$LAUNCH_AGENTS_DIR/com.quote0desk.tunnel.plist"

for label in com.quote0desk.server com.quote0desk.tunnel; do
  launchctl bootout "gui/$UID_NUM/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$UID_NUM" "$LAUNCH_AGENTS_DIR/$label.plist"
  launchctl enable "gui/$UID_NUM/$label"
done

echo "已安装，5 秒后检查状态："
sleep 5
launchctl list | grep quote0desk || echo "（没找到——看 data/*.err.log 排查）"
echo
echo "日志：$REPO_DIR/data/com.quote0desk.{server,tunnel}.{out,err}.log"
echo "隧道地址：$REPO_DIR/data/tunnel_daemon.log 里搜 nfc_base_url"
echo
echo "前提：$REPO_DIR/.env 里要有 DOT_API_KEY=dot_xxx...（参照 .env.example）"
