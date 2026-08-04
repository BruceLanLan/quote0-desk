#!/usr/bin/env python3
"""统一命令行入口：推卡片、看状态、下载当前渲染图自查。

用法：
  export DOT_API_KEY=dot_xxx...
  python3 cli.py hello                 # M1 验证：推一张最简卡
  python3 cli.py status                # 看设备状态
  python3 cli.py snapshot [out.png]    # 下载 renderInfo.current.image
  python3 cli.py push <card_module>    # 推 cards/ 下某张卡（每张卡需实现 build()），如 pet/liuyao/qimen/daily/status
  python3 cli.py set-todo <文字>        # 设置今日一件事
  python3 cli.py auto-cards a b c      # 设置调度器轮换哪些卡（不含 qiantong，那是 NFC 触发的）
  python3 cli.py arm / disarm          # 打开/关闭自动轮换（默认关闭，需要 server.py 常驻跑）
"""
import sys

import requests

import dot


def cmd_hello():
    d = dot.resolve_device_id()
    r = dot.push_text(d, title="quote0-desk", message="M1 骨架打通", signature="Hello Quote/0",
                       refresh_now=True, task_alias="M1 hello")
    print(r)
    if r["ok"]:
        cmd_snapshot()


def cmd_status():
    d = dot.resolve_device_id()
    print(dot.status(d))


def cmd_snapshot(out: str = "snapshot.png"):
    d = dot.resolve_device_id()
    s = dot.status(d)
    urls = s["renderInfo"]["current"]["image"]
    if not urls:
        print("当前没有渲染图 URL")
        return
    png = requests.get(urls[0], timeout=10).content
    with open(out, "wb") as f:
        f.write(png)
    print(f"已保存 {out}（来自 {urls[0]}）")


def cmd_push(card_name: str):
    from push import push_card
    print(push_card(card_name))


def cmd_set_todo(task: str):
    from providers.todo import set_task
    set_task(task)
    print(f"今日一件事已设为：{task}")


def cmd_auto_cards(*cards: str):
    import config
    config.update(auto_push_cards=list(cards))
    print(f"调度器轮换列表已设为：{list(cards)}（需要 arm 且 server.py 常驻运行才生效）")


def cmd_arm(on: bool):
    import config
    config.update(auto_push_enabled=on)
    print(f"自动轮换已{'开启' if on else '关闭'}（需要 server.py 常驻运行才真正生效）")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "hello":
        cmd_hello()
    elif cmd == "status":
        cmd_status()
    elif cmd == "snapshot":
        cmd_snapshot(*args)
    elif cmd == "push":
        cmd_push(*args)
    elif cmd == "set-todo":
        cmd_set_todo(" ".join(args))
    elif cmd == "auto-cards":
        cmd_auto_cards(*args)
    elif cmd == "arm":
        cmd_arm(True)
    elif cmd == "disarm":
        cmd_arm(False)
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
