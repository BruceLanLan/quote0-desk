"""Quote/0 官方 REST API 薄客户端。

对照 https://dot.mindreset.tech/developers 的 open API 系列。跟
pocket-prophet-dashboard/device.py 的定位不同——那边是逆向局域网接口，
这里是官方文档化的云端接口，鉴权、错误语义、超时策略都不一样，但延续
同一条工程纪律：**推送类操作永不抛异常，返回结构化 {ok, reason, hint}**，
供上层路由/CLI 直接用于文案，不需要 try/except 包一层。

已实测确认的事实见 docs/DEVICE-FACTS.md（M0 阶段产出）。
"""
from __future__ import annotations

import os

import requests

BASE_URL = "https://dot.mindreset.tech/api/authV2/open"

PROBE_TIMEOUT = 10   # 秒，读状态/列表
PUSH_TIMEOUT = 15    # 秒，text/image/canvas 推送
CONVERT_TIMEOUT = 20  # canvas 服务端渲染可能比纯文本慢

# 官方文档没提速率限制细节；先给个保守的连接超时，观察 M0 阶段是否触发限流。


class DotError(Exception):
    """编程错误：缺 key、缺设备号——不是设备侧的正常失败状态，值得抛出。"""


def _headers() -> dict:
    from config import api_key
    return {
        "Authorization": f"Bearer {api_key()}",
        "Content-Type": "application/json",
    }


def _get(path: str, timeout: int = PROBE_TIMEOUT) -> dict:
    """只读 GET。网络/HTTP 错误统一包成 DotError（调用方是内部代码，不是
    面向用户的推送路径，抛出比吞掉更合适——反正 M0/CLI 阶段需要看见真实报错）。
    """
    try:
        r = requests.get(f"{BASE_URL}{path}", headers=_headers(), timeout=timeout)
    except requests.RequestException as e:
        raise DotError(f"GET {path} 网络错误: {e}") from e
    if not r.ok:
        raise DotError(f"GET {path} 返回 HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def _post_structured(path: str, body: dict, timeout: int = PUSH_TIMEOUT) -> dict:
    """写入类 POST。永不抛异常，返回结构化结果：

      {"ok": True, "message": "..."}                     成功
      {"ok": False, "reason": "unauthorized", "hint": ...} 401/403，多半是 key 权限
      {"ok": False, "reason": "not_found", "hint": ...}    404，设备不存在或内容槽未创建
      {"ok": False, "reason": "bad_request", "hint": ...}  400，payload 有问题
      {"ok": False, "reason": "server_error", "hint": ...} 5xx，设备侧响应失败
      {"ok": False, "reason": "network_error", "hint": ...} 请求都没发出去/超时
    """
    try:
        r = requests.post(f"{BASE_URL}{path}", headers=_headers(), json=body, timeout=timeout)
    except requests.RequestException as e:
        return {"ok": False, "reason": "network_error", "hint": f"请求失败: {e}"}

    if r.status_code == 200:
        try:
            j = r.json()
        except ValueError:
            j = {}
        return {"ok": True, "message": j.get("message", ""), "raw": j}

    try:
        detail = r.json().get("message", r.text[:300])
    except ValueError:
        detail = r.text[:300]

    if r.status_code in (401, 403):
        return {"ok": False, "reason": "unauthorized", "hint": f"鉴权失败（{r.status_code}）：{detail}"}
    if r.status_code == 404:
        return {"ok": False, "reason": "not_found", "hint": f"设备或内容槽未找到：{detail}"}
    if r.status_code == 400:
        return {"ok": False, "reason": "bad_request", "hint": f"参数无效：{detail}"}
    return {"ok": False, "reason": "server_error", "hint": f"设备返回 HTTP {r.status_code}：{detail}"}


# ---- 设备发现与状态 ----

def list_devices() -> list[dict]:
    return _get("/devices")


def resolve_device_id() -> str:
    """优先读 config/env 里手填的序列号；没填且账号下只有一台设备时自动发现。"""
    from config import device_id as configured_id
    try:
        return configured_id()
    except RuntimeError:
        pass
    devices = list_devices()
    if len(devices) == 1:
        return devices[0]["id"]
    if not devices:
        raise DotError("账号下没有任何设备（GET /devices 为空）")
    raise DotError(f"账号下有 {len(devices)} 台设备，需要在 config/env 里手填 DOT_DEVICE_ID")


def status(device_id: str) -> dict:
    return _get(f"/device/{device_id}/status")


def get_settings(device_id: str) -> dict:
    return _get(f"/device/{device_id}/settings")


def update_settings(device_id: str, **fields) -> dict:
    return _post_structured(f"/device/{device_id}/settings", fields)


def list_content(device_id: str, task_type: str) -> list[dict]:
    """task_type: 'loop' 或 'fixed'。"""
    return _get(f"/device/{device_id}/{task_type}/list")


def next_content(device_id: str) -> dict:
    return _post_structured(f"/device/{device_id}/next", {})


def timezones() -> list[dict]:
    return _get("/timezones")


# ---- 三种渲染推送 ----

def push_text(device_id: str, *, title: str = None, message: str = None,
              signature: str = None, icon: str = None, link: str = None,
              styles: dict = None, task_key: str = None, task_alias=None,
              refresh_now: bool = True) -> dict:
    body = {"refreshNow": refresh_now}
    for k, v in (("title", title), ("message", message), ("signature", signature),
                 ("icon", icon), ("link", link), ("styles", styles),
                 ("taskKey", task_key), ("taskAlias", task_alias)):
        if v is not None:
            body[k] = v
    return _post_structured(f"/device/{device_id}/text", body)


def push_image(device_id: str, *, image: str, link: str = None, border: int = 0,
               dither_type: str = None, dither_kernel: str = None,
               task_key: str = None, task_alias=None, refresh_now: bool = True) -> dict:
    body = {"refreshNow": refresh_now, "image": image, "border": border}
    for k, v in (("link", link), ("ditherType", dither_type), ("ditherKernel", dither_kernel),
                 ("taskKey", task_key), ("taskAlias", task_alias)):
        if v is not None:
            body[k] = v
    return _post_structured(f"/device/{device_id}/image", body)


def push_canvas(device_id: str, *, data: dict, window_data: dict, layout_full: dict = None,
                link: str = None, border: int = 0, task_key: str = None,
                task_alias=None, refresh_now: bool = True) -> dict:
    body = {"refreshNow": refresh_now, "data": data, "windowData": window_data, "border": border}
    for k, v in (("layoutFull", layout_full), ("link", link),
                 ("taskKey", task_key), ("taskAlias", task_alias)):
        if v is not None:
            body[k] = v
    return _post_structured(f"/device/{device_id}/canvas", body, timeout=CONVERT_TIMEOUT)
