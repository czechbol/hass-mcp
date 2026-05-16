"""HomeAssistantView mounting the MCP server on HA's HTTP."""

from __future__ import annotations

import datetime as _dt
import enum as _enum
import json
import logging
from types import MappingProxyType
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import (
    CONF_RATE_LIMIT_PER_MINUTE,
    DEFAULT_RATE_LIMIT_PER_MINUTE,
    DOMAIN,
    VIEW_URL,
)
from .protocol import dispatch
from .rate_limit import RateLimiter

_LOGGER = logging.getLogger(__name__)


def _json_default(o: Any) -> Any:
    if isinstance(o, MappingProxyType):
        return dict(o)
    if isinstance(o, (set, frozenset)):
        return sorted(o, key=str)
    if isinstance(o, (_dt.datetime, _dt.date, _dt.time)):
        return o.isoformat()
    if isinstance(o, _dt.timedelta):
        return o.total_seconds()
    if isinstance(o, _enum.Enum):
        return o.value
    if hasattr(o, "as_dict") and callable(o.as_dict):
        try:
            return o.as_dict()
        except Exception:  # noqa: BLE001
            pass
    if hasattr(o, "_asdict") and callable(o._asdict):
        try:
            return o._asdict()
        except Exception:  # noqa: BLE001
            pass
    return str(o)


def _json_response(payload: Any, status: int = 200) -> web.Response:
    text = json.dumps(payload, default=_json_default, ensure_ascii=False)
    return web.Response(text=text, status=status, content_type="application/json")


class MCPView(HomeAssistantView):
    """MCP Streamable HTTP endpoint (POST-only, stateless).

    Per spec, a server may omit SSE entirely and respond to every POST with
    either a JSON response (request) or 202 Accepted (notification only).
    """

    url = VIEW_URL
    name = "api:hass_mcp"
    requires_auth = True
    cors_allowed = False

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._limiter: RateLimiter | None = None

    def _get_limiter(self) -> RateLimiter | None:
        opts = self._hass.data.get(DOMAIN, {}).get("options", {})
        per_minute = opts.get(CONF_RATE_LIMIT_PER_MINUTE, DEFAULT_RATE_LIMIT_PER_MINUTE)
        if not per_minute or per_minute <= 0:
            return None
        if self._limiter is None or self._limiter.max_calls != per_minute:
            self._limiter = RateLimiter(per_minute, 60.0)
        return self._limiter

    async def post(self, request: web.Request) -> web.StreamResponse:
        limiter = self._get_limiter()
        if limiter is not None:
            auth = request.headers.get("Authorization", "")
            key = auth[-32:] if auth else (request.remote or "anon")
            allowed, retry = limiter.check(key)
            if not allowed:
                return web.Response(
                    status=429,
                    headers={"Retry-After": str(int(retry) + 1)},
                    text=f"rate limit exceeded; retry in {retry:.1f}s",
                )

        raw = await request.read()
        if not raw:
            return _bad_request("empty body")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError as e:
            return _bad_request(f"invalid JSON: {e}")

        response = await dispatch(self._hass, body)
        if response is None:
            return web.Response(status=202)

        return _json_response(response)

    async def get(self, request: web.Request) -> web.StreamResponse:
        return web.Response(
            status=405,
            headers={"Allow": "POST"},
            text="GET not supported; use POST for Streamable HTTP",
        )


def _bad_request(message: str) -> web.Response:
    return _json_response(
        {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32700, "message": message},
        },
        status=400,
    )
