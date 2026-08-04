"""ASCII 宠物造型：移植自官方 anthropics/claude-desktop-buddy（MIT 许可，
Copyright 2026 Anthropic, PBC）——Claude Code / Claude Cowork 官方的桌宠
固件项目（M5StickC Plus + ESP32），用户点名要求"融合"这个官方项目，
不再用之前反向工程拿到的简化版素材（milind-soni/claude-pets）。

原作每个状态是 5-10 帧的连续动画（`src/buddies/duck.cpp`），配合物理屏幕
实时刷新和粒子效果（Z 字漂浮、气泡上升、彩带、爱心）。Quote/0 是静态
墨水屏、没有连续刷新能力，这里从每个状态摘 2-3 帧当"轮换的静态快照"，
不追求还原动画本身，帧内容原样保留（没有改动画面本身的字符）。

状态语义直接沿用官方定义（源文件注释）：
- `sleep`     桥接不在线 → 我们映射成"buddy-bridge 不可用且长时间无活动"
- `idle`      在线但没有紧急事项
- `busy`      会话正在跑 → buddy-bridge 的 running > 0
- `attention` 有操作在等审批 → buddy-bridge 的 waiting > 0
- `celebrate` 里程碑（原作每 50K tokens 升一级）→ 复用同样的触发点
- `heart`     原作是"5 秒内被批准"的奖励反应 → 这里先接到 NFC 摸摸
  （`/t/pet_pat`），以后接上"贴一下批准工具调用"功能时同样触发这个状态，
  两者都是"我很开心"，共用一套素材没有问题
- `dizzy`（摇晃设备触发）—— Quote/0 没有加速度计，没有对应的物理动作
  可以触发，没有移植

具体状态判定逻辑在 `providers/pet.py`，这个文件只管素材。
只保留 duck 一种造型（原作有 18 种），选宠物是后续功能，不在这次范围。
"""

SPECIES = {
    "duck": {
        "sleep": [
            ["            ", "            ", "    __      ", "  <(-_)_)   ", " ~~~~~~~~~~ "],
            ["            ", "    __      ", "  <(-_)_)   ", "  ~~~~~~~~  ", "   ~~~~~~   "],
        ],
        "idle": [
            ["            ", "    __      ", "  <(o )___  ", "   (  ._>   ", "    `--´    "],
            ["            ", "    __      ", "  <(- )___  ", "   (  ._>   ", "    `--´    "],
            ["            ", "    __      ", " <<(o )___  ", "   (  ._>   ", "    `--´    "],
        ],
        "busy": [
            ["            ", "    __      ", "  <(o )___  ", "   (  ._>   ", "  ~ `--´    "],
            ["            ", "    __      ", "  <(o )___  ", "   (  ._>   ", "    `--´ ~  "],
            ["      ?     ", "    __      ", "  <(o )___  ", "   (  ._>   ", "    `--´    "],
        ],
        "attention": [
            ["    __      ", "  <(O )     ", "  (    )___ ", "   (  ._>   ", "    `--´    "],
            ["    __      ", " <<(O )     ", "  (    )___ ", "   (  ._>   ", "    `--´    "],
            ["    __      ", "  <( O)     ", "  (    )___ ", "   (  ._>   ", "    `--´    "],
        ],
        "celebrate": [
            ["  \\^ __ ^/  ", "   <(^ )___ ", "   (  ._>   ", "    `--´    ", "  ~~~~~~~~  "],
            ["    \\__/    ", "    __      ", "  <(^ )___  ", " /(  ._>\\   ", "    `--´    "],
        ],
        "heart": [
            ["            ", "    __      ", "  <(<3)___  ", "   (  ._>   ", "    `--´    "],
            ["            ", "    __      ", "  <(^#)___  ", "   (  ._>   ", "    `--´    "],
        ],
    },
}


def render_frame(species: str, state: str, frame_index: int) -> list[str]:
    species_frames = SPECIES.get(species, SPECIES["duck"])
    frames = species_frames.get(state) or species_frames["idle"]
    return list(frames[frame_index % len(frames)])
