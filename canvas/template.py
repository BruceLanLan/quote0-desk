"""文本卡片的数据形状：标题/正文/footer 三段式，喂给 Text API。

2026-08-01 之前这里还有个 `simple_card()` 生成 Canvas API 的 windowData——
后来发现设备 loop 槽位有硬上限（3 个，用户已经用掉一个给官方新闻内容），
账号这边只留了 Text API + Image API 两个槽给我们用，Canvas 槽被顶掉后
一直没能再要回来（见 docs/DEVICE-FACTS.md）。Text API 原生支持 `\n` 换行、
自动折行，`simple_data()` 产出的 title/message/footer 直接映射
`push_text()` 的 title/message/signature，不用再画 Tailwind 布局，
`simple_card()` 整个删掉，不留没有对应槽位的死代码。
"""
from __future__ import annotations


def simple_data(*, badge: str = "", title: str = "", message: str = "", footer: str = "") -> dict:
    return {"badge": badge, "title": title, "message": message, "footer": footer}
