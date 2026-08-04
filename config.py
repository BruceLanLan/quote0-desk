"""运行时配置：读写 config.json，缺字段时用默认值，不崩溃。

移植自 pocket-prophet-dashboard 的模式（DEFAULTS + load/save/update）。

跟上个项目不同的地方：**密钥类信息不走这个文件**。API Key 只认环境变量
`DOT_API_KEY`；设备序列号可以放这里（config.json 已在 .gitignore 里，
不会进仓库），但更推荐同样走环境变量 `DOT_DEVICE_ID`——因为设备只有一台，
`GET /devices` 也能自动发现，不强依赖手填。
"""
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULTS = {
    "device_id": "",  # 留空则启动时用 GET /devices 自动发现（前提：账号下只有一台）
    "nfc_base_url": "",  # NFC 回调服务的可达地址，例：http://<LAN_IP>:5252（局域网 IP 会变，改这一处，不用逐张卡改）
    # ⚠️ 下面这四项目前没有任何代码在读（2026-08-04 核对）：天气卡还没做；
    # 「哪些卡生效」实际是靠 auto_push_cards 决定的，enabled_cards 是早期设计
    # 的残留；箴言机最后选了纯种子缓存、不调模型，那两个成本闸参数因此一直没
    # 派上用场。留着是因为对应功能还在路线图上，但**故意不给它们做设置页入口**
    # ——后台摆一个拧了不起作用的旋钮，比没有旋钮更糟。等哪张卡真的开始读它们
    # 了，再一起把 UI 补上。
    "weather_city": "深圳",
    "enabled_cards": ["proverb"],
    "proverb_daily_generations": 6,
    "proverb_cache_min": 2,
    # 自动推送：默认关闭，需显式布防（同 pocket-prophet 的教训）。
    "auto_push_enabled": False,
    "auto_push_interval_minutes": 10,
    "auto_push_cards": [],
    "_auto_push_last_card": None,
    # 屏上宠物造型，合法值见 render/pet_sprites.py 的 SPECIES（控制台设置页
    # 用 /api/pet_species 拿这份列表填下拉框）。默认鸭子＝原来硬编码的那一种。
    "pet_species": "duck",
    # ── 路径类配置 ──
    # 这几项以前是各 provider 文件里的模块级常量，只能改源码。默认值跟原来
    # 硬编码的完全一致，改成配置项不改变任何现有行为，只是多了一个后台入口。
    # 一律用 `~` 开头的形式存，读的时候 expanduser——config.json 万一被贴到
    # 别处也不会带出本机用户名。
    "pet_repos": ["~/dev/quote0-desk", "~/dev/pocket-prophet-dashboard"],
    "capsule_repos": ["~/dev/quote0-desk", "~/dev/pocket-prophet-dashboard"],
    "beacon_lighter_dir": "~/lighter-scalper",
    "beacon_stock_radar_dir": "~/dev/stock-radar",
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                cfg.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return cfg


def save(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def update(**kwargs):
    cfg = load()
    cfg.update(kwargs)
    save(cfg)
    return cfg


def path_setting(key: str) -> str:
    """读一个路径类配置，展开 `~`。空字符串当"没配"处理、退回 DEFAULTS 里的
    默认值——不能把空串当成根目录去扫，那会让 provider 扫整个磁盘。"""
    raw = str(load().get(key) or "").strip()
    if not raw:
        raw = str(DEFAULTS.get(key) or "")
    return os.path.expanduser(raw) if raw else ""


def path_list_setting(key: str) -> list[str]:
    """读一个路径列表配置（仓库列表这类），逐个展开 `~`、丢掉空项。整个列表
    为空同样退回默认值——用户在后台把输入框清空，意思大概率是"恢复默认"，
    不是"一个仓库都不扫"（真想关掉这张卡，从 enabled_cards 里去掉才对）。"""
    raw = load().get(key)
    if not isinstance(raw, list):
        raw = []
    items = [str(p).strip() for p in raw if str(p).strip()]
    if not items:
        items = [str(p) for p in DEFAULTS.get(key, [])]
    return [os.path.expanduser(p) for p in items]


def api_key() -> str:
    """API Key 只认环境变量，绝不落 config.json——即便 config.json 已被
    .gitignore 排除，密钥也不应该以明文形式常驻磁盘里的项目文件。"""
    key = os.environ.get("DOT_API_KEY", "")
    if not key:
        raise RuntimeError(
            "未设置 DOT_API_KEY 环境变量。运行前先 export DOT_API_KEY=dot_xxx..."
        )
    return key


def device_id() -> str:
    """设备序列号：优先环境变量 DOT_DEVICE_ID，其次 config.json，都没有则报错
    （调用方可以退而用 dot.list_devices() 自动发现，见 dot.py 的 resolve_device_id）。
    """
    env_id = os.environ.get("DOT_DEVICE_ID", "")
    if env_id:
        return env_id
    cfg_id = load().get("device_id", "")
    if cfg_id:
        return cfg_id
    raise RuntimeError("未配置设备序列号，且未走自动发现。")


def nfc_base_url() -> str:
    """NFC 回调服务的可达地址（局域网 IP:port 或公网地址），不含末尾斜杠。

    这一处是 2026-08-04 真机测试踩过坑之后加的：之前每张卡的 link 各自
    硬编码或干脆留空（"M2 阶段再填" 的 TODO 一直没人填），加上局域网 IP
    换了没同步更新，导致 NFC 贴一下要么打开死链接、要么直接没有 link 可点。
    改成从这一个配置读，局域网 IP 变了只改这一处，所有卡的 link 跟着更新。

    留空不是报错条件——很多卡（状态灯、时间胶囊、信标）本来就不需要 NFC
    交互入口，调用方按"没配就不生成 link"处理，不是"配置缺失就崩"。
    """
    env_url = os.environ.get("NFC_BASE_URL", "").rstrip("/")
    if env_url:
        return env_url
    return load().get("nfc_base_url", "").rstrip("/")
