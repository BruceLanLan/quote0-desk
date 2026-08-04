#!/bin/bash
# launchd 拉起的 cloudflared 隧道守护脚本。cloudflared quick tunnel
# (trycloudflare.com) 每次启动地址都会变，之前只能手动跑、手动抄地址、
# 手动 export NFC_BASE_URL——这个脚本把"抄地址"这一步自动化：解析
# cloudflared 自己打印的 URL，写进 config.json 的 nfc_base_url，
# server.py 的 config.nfc_base_url() 下次调用就读到新值。
#
# cloudflared 进程本身退出（网络断开、进程被杀……）这个脚本也会跟着退出，
# launchd 的 KeepAlive 负责重启整个脚本，重启就是一轮新的隧道 + 新地址，
# 不需要这个脚本自己写重试循环。
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p data

CLOUDFLARED_BIN="${CLOUDFLARED_BIN:-/opt/homebrew/bin/cloudflared}"
# 同 run_server.sh 的理由：写死解释器，不靠 PATH 里排在前面的
# /opt/homebrew/bin/python3（没装 config.py 需要的任何依赖）。
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
LOCAL_URL="${LOCAL_URL:-http://localhost:5252}"
LOG="data/tunnel_daemon.log"

echo "[tunnel_daemon] $(date '+%F %T') 启动，目标 $LOCAL_URL" >>"$LOG"

"$CLOUDFLARED_BIN" tunnel --url "$LOCAL_URL" 2>&1 | while IFS= read -r line; do
  echo "$line" >>"$LOG"
  url=$(echo "$line" | grep -oE 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' || true)
  if [ -n "$url" ]; then
    # $url 传成 argv 而不是拼进 -c 的代码字符串——避免 shell 插值直接
    # 变成可执行的 Python 代码（即便 grep 已经限定了 URL 的形状，公开
    # 仓库上这种"拼字符串成代码"的写法本身就不该有）。
    "$PYTHON_BIN" -c "import sys, config; config.update(nfc_base_url=sys.argv[1])" "$url"
    echo "[tunnel_daemon] $(date '+%F %T') nfc_base_url -> $url" >>"$LOG"
  fi
done

echo "[tunnel_daemon] $(date '+%F %T') cloudflared 退出，等待 launchd 重启" >>"$LOG"
