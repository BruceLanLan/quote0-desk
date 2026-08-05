"""Quote/0 platform adapter (Hermes plugin) — outbound-only e-ink display.

Sends agent messages and cron job results to a physical Quote/0 e-ink desk
device via the local quote0-desk service
(https://github.com/BruceLanLan/quote0-desk), which owns the actual Dot
cloud API credentials and NFC-callback link generation.

This adapter never receives inbound messages — Quote/0 has no chat UI,
just a 296x152 e-ink panel and an NFC tap. There is no stream to
maintain, so ``connect()``/``disconnect()`` are bookkeeping only; all
real work happens in ``send()``. quote0-desk being offline at connect
time does not block gateway startup — reachability is only checked (and
only matters) at send time, same optional-dependency discipline as
quote0-desk's own ``providers/buddy.py``.

Security note (see quote0-desk's private Hermes integration plan,
decisions D1-D3): this adapter never sets a ``link`` field — quote0-desk's
own card layer generates (or omits) the NFC callback link, so a
prompt-injected agent cannot turn a physical tap into a phishing
redirect. The on-screen footer/signature is fixed by quote0-desk's card
(always "Hermes Agent"), not by anything sent here. There is exactly one
fixed destination (``chat_id`` is accepted for interface compatibility
but ignored) — no per-message routing, no identity derived from message
content.

Configuration (env vars, all read at adapter construct time):

    QUOTE0_ENABLED       "true" to enable this adapter (required)
    QUOTE0_DESK_URL      quote0-desk base URL (default: http://127.0.0.1:5252)
    QUOTE0_HOME_CHANNEL  any non-empty value enables cron deliver=quote0
"""

import logging
import os
from typing import Any, Dict, List, Optional

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore[assignment]

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, SendResult

logger = logging.getLogger(__name__)

DEFAULT_URL = "http://127.0.0.1:5252"
MAX_MESSAGE_LENGTH = 500  # 跟 quote0-desk 的 providers/hermes_inbox.py 保持一致
INBOX_PATH = "/api/hermes_inbox"


def _base_url() -> str:
    return (os.getenv("QUOTE0_DESK_URL", "").strip() or DEFAULT_URL).rstrip("/")


def check_requirements() -> bool:
    """是否启用这个适配器——只看用户是否显式 opt-in（QUOTE0_ENABLED），不做
    网络探测。探测放到每次 send() 时做：quote0-desk 没起来不该阻止整个
    gateway 启动，这条纪律照抄 ntfy 适配器的 check_requirements()。"""
    if not HTTPX_AVAILABLE:
        return False
    return os.getenv("QUOTE0_ENABLED", "").strip().lower() in ("1", "true", "yes")


def validate_config(config) -> bool:
    return check_requirements()


def is_connected(config) -> bool:
    return check_requirements()


class Quote0Adapter(BasePlatformAdapter):
    """Quote/0 e-ink 适配器：outbound-only，没有 inbound 消息流要维护。"""

    MAX_MESSAGE_LENGTH = MAX_MESSAGE_LENGTH

    def __init__(self, config: PlatformConfig):
        platform = Platform("quote0")
        super().__init__(config=config, platform=platform)
        self._client: Optional["httpx.AsyncClient"] = None

    async def connect(self) -> bool:
        """没有 inbound 流要维护——quote0-desk 当下在不在线不影响这一步，
        真正的可达性判断留到每次 send() 时做（可选依赖，优雅降级）。"""
        if not HTTPX_AVAILABLE:
            logger.warning("[%s] httpx not installed", self.name)
            return False
        self._client = httpx.AsyncClient(timeout=10.0)
        self._mark_connected()
        logger.info("[%s] Ready — will POST to %s%s on send()", self.name, _base_url(), INBOX_PATH)
        return True

    async def disconnect(self) -> None:
        self._mark_disconnected()
        if self._client:
            await self._client.aclose()
            self._client = None

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """推一条消息到 quote0-desk 的 /api/hermes_inbox。

        只传 message 字段——不构造、不转发任何 link 相关的东西。服务端
        接口本来就不接受 link 参数，这里再确认一遍是双重保证：agent 没有
        任何路径能把内容之外的东西塞进这次推送（安全设计决策 D1）。
        """
        if not self._client:
            return SendResult(success=False, error="HTTP client not initialized")

        body = content[:self.MAX_MESSAGE_LENGTH]
        url = f"{_base_url()}{INBOX_PATH}"
        try:
            resp = await self._client.post(url, json={"message": body})
        except httpx.TimeoutException:
            return SendResult(success=False, error="quote0-desk 请求超时（服务是否在跑？）")
        except Exception as e:
            return SendResult(success=False, error=f"quote0-desk 不可达: {e}")

        if resp.status_code >= 300:
            return SendResult(success=False, error=f"HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            data = resp.json()
        except Exception:
            data = {}
        if not data.get("ok"):
            return SendResult(success=False, error=data.get("hint") or "quote0-desk 返回了失败")
        return SendResult(success=True, message_id=None)

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        """Quote/0 没有"正在输入"这种交互面，no-op。"""
        pass

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        return {"name": "Quote/0 desk", "type": "dm"}


async def _standalone_send(
    pconfig,
    chat_id: str,
    message: str,
    *,
    thread_id: Optional[str] = None,
    media_files: Optional[List[str]] = None,
    force_document: bool = False,
) -> Dict[str, Any]:
    """cron 与 gateway 不同进程时的带外投递。没有这个钩子，deliver=quote0
    的 cron job 会报 "No live adapter for platform 'quote0'"（照 ntfy 的
    _standalone_send 同一套纪律）。"""
    if not HTTPX_AVAILABLE:
        return {"error": "quote0 standalone send: httpx not installed"}
    body = message[:MAX_MESSAGE_LENGTH]
    url = f"{_base_url()}{INBOX_PATH}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={"message": body})
        if resp.status_code >= 300:
            return {"error": f"quote0-desk HTTP {resp.status_code}: {resp.text[:200]}"}
        data = resp.json()
        if not data.get("ok"):
            return {"error": data.get("hint") or "quote0-desk 返回了失败"}
        return {"success": True, "platform": "quote0", "chat_id": "quote0"}
    except Exception as e:
        return {"error": f"quote0 standalone send failed: {e}"}


def register(ctx) -> None:
    """Plugin entry point — called by the Hermes plugin system at startup."""
    ctx.register_platform(
        name="quote0",
        label="Quote/0",
        adapter_factory=lambda cfg: Quote0Adapter(cfg),
        check_fn=check_requirements,
        validate_config=validate_config,
        is_connected=is_connected,
        required_env=["QUOTE0_ENABLED"],
        install_hint="pip install httpx   # already a Hermes dependency",
        # cron `deliver=quote0` 投递支持——只有一个固定 channel，环境变量的值
        # 本身没有语义，非空就代表"启用了 home channel"。
        cron_deliver_env_var="QUOTE0_HOME_CHANNEL",
        # 带外投递（cron 与 gateway 不同进程时）。没有这个钩子 deliver=quote0
        # 会报 "No live adapter for platform 'quote0'"。
        standalone_sender_fn=_standalone_send,
        max_message_length=MAX_MESSAGE_LENGTH,
        emoji="🖥️",
        # quote0-desk 只认一条固定消息，没有可以泄露的用户标识。
        pii_safe=True,
        allow_update_command=False,
        platform_hint=(
            "You are sending to a Quote/0 physical e-ink desk display (296x152, "
            "black & white). Keep messages short and plain text — there is no "
            "markdown rendering and no way to scroll. This is outbound-only: "
            "the device cannot reply, so do not expect or wait for a response "
            "through this channel."
        ),
    )
