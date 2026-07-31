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
    "weather_city": "深圳",
    "enabled_cards": ["proverb"],  # 陆续加入 daily/liuyao/qimen/status/pet/todo/capsule/beacon
    # 箴言机成本闸（docs/PLAN 的教训：不能"刷一次屏调一次模型"）：
    # 每天定时生成几条缓存，NFC「换一句」和自动刷新都只读缓存，
    # 缓存见底才补生成。
    "proverb_daily_generations": 6,
    "proverb_cache_min": 2,
    # 自动推送：默认关闭，需显式布防（同 pocket-prophet 的教训）。
    "auto_push_enabled": False,
    "auto_push_interval_minutes": 10,
    "auto_push_cards": [],
    "_auto_push_last_card": None,
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
