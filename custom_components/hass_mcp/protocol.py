"""MCP JSON-RPC protocol dispatch.

Implements a minimal subset of the Model Context Protocol sufficient for
Streamable HTTP clients that use POST request/response only:

* ``initialize``
* ``initialized`` notification (acknowledged)
* ``ping``
* ``tools/list``
* ``tools/call``

Subscriptions, resources, prompts, sampling, and completions are not
implemented — clients that don't strictly require them will function.
"""

from __future__ import annotations

import datetime as _dt
import enum as _enum
import json
import logging
from types import MappingProxyType
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_ALLOW_DESTRUCTIVE,
    CONF_ALLOW_FIRE_EVENT,
    CONF_ALLOW_WRITE,
    DOMAIN,
    PROTOCOL_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
)
from .registry import TOOLS, ToolDef

_LOGGER = logging.getLogger(__name__)

# JSON-RPC error codes per spec + MCP additions.
_PARSE_ERROR = -32700
_INVALID_REQUEST = -32600
_METHOD_NOT_FOUND = -32601
_INVALID_PARAMS = -32602
_INTERNAL_ERROR = -32603


class JsonRpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def _err(req_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": error}


def _ok(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


async def dispatch(hass: HomeAssistant, body: Any) -> Any | None:
    """Dispatch a single JSON-RPC message or a batch. Returns the response, or
    ``None`` for notifications (no response expected).
    """
    if isinstance(body, list):
        if not body:
            return _err(None, _INVALID_REQUEST, "empty batch")
        responses = [await _dispatch_one(hass, m) for m in body]
        filtered = [r for r in responses if r is not None]
        return filtered or None
    return await _dispatch_one(hass, body)


async def _dispatch_one(hass: HomeAssistant, msg: Any) -> dict[str, Any] | None:
    if not isinstance(msg, dict):
        return _err(None, _INVALID_REQUEST, "message must be an object")
    if msg.get("jsonrpc") != "2.0":
        return _err(msg.get("id"), _INVALID_REQUEST, "jsonrpc must be '2.0'")
    method = msg.get("method")
    if not isinstance(method, str):
        return _err(msg.get("id"), _INVALID_REQUEST, "missing method")
    req_id = msg.get("id")
    is_notification = "id" not in msg
    params = msg.get("params") or {}
    if not isinstance(params, dict):
        return _err(req_id, _INVALID_PARAMS, "params must be an object")

    try:
        result = await _route(hass, method, params)
    except JsonRpcError as e:
        if is_notification:
            return None
        return _err(req_id, e.code, e.message, e.data)
    except Exception as e:
        _LOGGER.exception("Unhandled error in MCP method %s", method)
        if is_notification:
            return None
        return _err(req_id, _INTERNAL_ERROR, f"{type(e).__name__}: {e}")

    if is_notification:
        return None
    return _ok(req_id, result)


async def _route(hass: HomeAssistant, method: str, params: dict[str, Any]) -> Any:
    if method == "initialize":
        return _initialize()
    if method in ("notifications/initialized", "initialized"):
        return None  # ignored, no result
    if method == "ping":
        return {}
    if method == "tools/list":
        return _tools_list(params)
    if method == "tools/call":
        return await _tools_call(hass, params)
    # Resources/prompts/sampling — advertise empty so spec-compliant clients still work.
    if method == "resources/list":
        return {"resources": []}
    if method == "resources/templates/list":
        return {"resourceTemplates": []}
    if method == "prompts/list":
        return {"prompts": []}
    raise JsonRpcError(_METHOD_NOT_FOUND, f"method not found: {method}")


def _initialize() -> dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {
            "tools": {"listChanged": False},
        },
        "serverInfo": {
            "name": SERVER_NAME,
            "version": SERVER_VERSION,
        },
        "instructions": (
            "Home Assistant generic-tools MCP. Read state with ha_list_states / "
            "ha_get_state. Drive devices with ha_call_service. Render templates "
            "with ha_render_template. Inspect history with ha_history / ha_logbook. "
            "Manage integrations with ha_config_entries and ha_config_flow."
        ),
    }


def _tools_list(_params: dict[str, Any]) -> dict[str, Any]:
    # Pagination cursor not implemented — emit all in one page.
    return {"tools": [t.to_listing() for t in TOOLS.values()]}


async def _tools_call(hass: HomeAssistant, params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    if not isinstance(name, str):
        raise JsonRpcError(_INVALID_PARAMS, "tools/call requires string 'name'")
    args = params.get("arguments") or {}
    if not isinstance(args, dict):
        raise JsonRpcError(_INVALID_PARAMS, "'arguments' must be an object")
    tool_def = TOOLS.get(name)
    if tool_def is None:
        raise JsonRpcError(_METHOD_NOT_FOUND, f"unknown tool: {name}")

    if not _gate(hass, tool_def):
        return _tool_error(
            f"tool '{name}' is disabled by integration options "
            f"(allow_write/allow_destructive/allow_fire_event); enable it in HA UI"
        )

    write_kind = (
        "destructive"
        if tool_def.requires_destructive
        else "write"
        if tool_def.requires_write
        else "read"
    )
    _LOGGER.info("hass_mcp tools/call %s [%s]", name, write_kind)

    try:
        result = await tool_def.handler(hass, **args)
    except _ToolError as e:
        return _tool_error(str(e))
    except TypeError as e:
        # Bad argument shape after JSON Schema (we don't enforce schema strictly here).
        return _tool_error(f"invalid arguments: {e}")
    except Exception as e:
        _LOGGER.exception("Tool %s failed", name)
        return _tool_error(f"{type(e).__name__}: {e}")

    return _tool_success(result)


def _gate(hass: HomeAssistant, t: ToolDef) -> bool:
    opts = hass.data.get(DOMAIN, {}).get("options", {})
    if t.requires_destructive and not opts.get(CONF_ALLOW_DESTRUCTIVE, False):
        return False
    if t.requires_fire_event and not opts.get(CONF_ALLOW_FIRE_EVENT, False):
        return False
    if t.requires_write and not opts.get(CONF_ALLOW_WRITE, True):
        return False
    return True


class _ToolError(Exception):
    """Raised by tool handlers to produce an actionable isError response."""


def _tool_success(result: Any) -> dict[str, Any]:
    text = _safe_json(result)
    out: dict[str, Any] = {
        "content": [{"type": "text", "text": text}],
        "isError": False,
    }
    if isinstance(result, dict):
        out["structuredContent"] = result
    return out


def _tool_error(message: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": message}],
        "isError": True,
    }


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
    return str(o)


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, default=_json_default, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return repr(value)


# Re-export for tool modules.
ToolError = _ToolError
