#!/bin/bash
# launchd 拉起 server.py 用的包装脚本。DOT_API_KEY 这类密钥不写进 plist
# （plist 是明文 XML，写进去等于把密钥摊在磁盘上一份新的），改成从仓库根
# 目录的 .env 读（.env 已在 .gitignore，不进仓库）。
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# 写死解释器而不是靠 PATH 里的 python3——本机 /opt/homebrew/bin/python3
# 是没装依赖的 Homebrew Python 3.14，真正装了 flask/requests/Pillow 的是
# /usr/bin/python3（CommandLineTools 3.9），launchd 的 PATH 顺序会选错。
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
exec "$PYTHON_BIN" server.py
