"""Canvas API 通用模板：标题/正文/footer 三段式布局，仿官方文档示例结构。

296×152 横屏，字号下限 12px（见 docs/DEVICE-FACTS.md P5）。这个模板给
「一句话/一段信息」类的卡复用（箴言、日课摘要、状态灯、承诺牌、时间胶囊、
信标），不同卡只需要传不同的 data 字典，不用各自重写 windowData 结构。

需要逐像素控制的卡（六爻爻线、奇门九宫格、宠物造型）不用这个模板，走
render/ 目录下的本地 PIL 渲染 + Image API。
"""
from __future__ import annotations


def simple_card(*, badge: str = "", title: str = "", message: str = "",
                 footer: str = "", title_size: int = 22, message_size: int = 14,
                 footer_size: int = 12) -> dict:
    """返回 push_canvas 需要的 window_data 结构（不含 data，调用方自己传
    对应的 data 字典给 push_canvas，这里的 windowData 用 {{get inputData ...}}
    引用同名字段，方便同一个模板配不同 data 复用）。
    """
    children = []

    if badge:
        children.append({
            "type": "div",
            "props": {
                "tw": "flex flex-row items-center justify-between shrink-0 text-10-chillduansans",
                "children": [{
                    "type": "span",
                    "props": {"tw": "font-bold", "children": "{{get inputData \"badge\" default=\"\"}}"},
                }],
            },
        })

    body_children = []
    if title:
        body_children.append({
            "type": "div",
            "props": {
                "tw": f"text-{title_size}-chillduansans font-bold leading-none min-w-0",
                "style": {"lineClamp": 2, "overflow": "hidden", "textOverflow": "ellipsis"},
                "children": "{{get inputData \"title\" default=\"\"}}",
            },
        })
    if message:
        # whiteSpace: pre-line 是让 \n 真正换行的关键——实测确认过 Canvas 文本节点
        # 默认会把 \n 吃掉连成一行，不加这个 style，多行文案全部现出原形写在一起。
        body_children.append({
            "type": "div",
            "props": {
                "tw": f"text-{message_size}-chillduansans leading-[1.2] min-w-0",
                "style": {"lineClamp": 4, "overflow": "hidden", "textOverflow": "ellipsis",
                          "whiteSpace": "pre-line"},
                "children": "{{get inputData \"message\" default=\"\"}}",
            },
        })
    children.append({
        "type": "div",
        "props": {
            "tw": "flex flex-col flex-1 min-h-0 justify-center gap-[4px]",
            "children": body_children,
        },
    })

    if footer:
        children.append({
            "type": "div",
            "props": {
                "tw": f"flex flex-row items-center text-{footer_size}-chillduansans shrink-0",
                "style": {"overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap"},
                "children": "{{get inputData \"footer\" default=\"\"}}",
            },
        })

    return {
        "default": [{
            "type": "div",
            "props": {
                "tw": "flex flex-col w-full h-full min-w-0 min-h-0 bg-white text-black gap-[6px] p-[10px]",
                "children": children,
            },
        }],
    }


def simple_data(*, badge: str = "", title: str = "", message: str = "", footer: str = "") -> dict:
    return {"badge": badge, "title": title, "message": message, "footer": footer}
