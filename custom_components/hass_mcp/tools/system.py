"""ha_system — core config, health, and log introspection."""

from __future__ import annotations

import os
from typing import Any

from homeassistant.core import HomeAssistant

from ..protocol import ToolError
from ..registry import LIMIT_FIELD, OFFSET_FIELD, paginate, schema, tool
from ..ws import WsCallError, ws_call

_OPS = (
    "get_config",
    "check_config",
    "get_health",
    "read_error_log",
    "read_system_log",
    "clear_system_log",
)


@tool(
    name="ha_system",
    description=(
        "Inspect the Home Assistant system. "
        "op=get_config (core config: version, location, components, URLs, units); "
        "op=check_config (validate configuration.yaml without restarting); "
        "op=get_health (aggregate system_health from all integrations); "
        "op=read_error_log (tail the on-disk home-assistant.log file); "
        "op=read_system_log (the in-memory log of errors/warnings, filterable); "
        "op=clear_system_log (clear that in-memory log)."
    ),
    input_schema=schema(
        properties={
            "op": {"type": "string", "enum": list(_OPS)},
            "lines": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5000,
                "default": 200,
                "description": "op=read_error_log.",
            },
            "level": {
                "type": "string",
                "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                "description": "op=read_system_log filter.",
            },
            "logger_prefix": {
                "type": "string",
                "description": "op=read_system_log filter (logger-name prefix).",
            },
            "limit": LIMIT_FIELD,
            "offset": OFFSET_FIELD,
        },
        required=["op"],
    ),
    read_only=False,
)
async def ha_system(
    hass: HomeAssistant,
    op: str,
    lines: int = 200,
    level: str | None = None,
    logger_prefix: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if op == "get_config":
        return hass.config.as_dict()

    if op == "check_config":
        return await _check_config(hass)

    if op == "get_health":
        return await _get_health(hass)

    if op == "read_error_log":
        return await _read_error_log(hass, lines)

    if op == "read_system_log":
        try:
            entries = await ws_call(hass, "system_log/list")
        except WsCallError as e:
            raise ToolError(str(e)) from e
        rows = list(entries or [])
        if level:
            rows = [r for r in rows if r.get("level") == level]
        if logger_prefix:
            rows = [r for r in rows if (r.get("name") or "").startswith(logger_prefix)]
        return paginate(rows, limit, offset)

    if op == "clear_system_log":
        try:
            await hass.services.async_call("system_log", "clear", {}, blocking=True)
        except Exception as e:
            raise ToolError(f"clear failed: {e}") from e
        return {"cleared": True}

    raise ToolError(f"unknown op '{op}'")


async def _check_config(hass: HomeAssistant) -> dict[str, Any]:
    try:
        from homeassistant.components.config.core import async_check_ha_config_file
    except ImportError:
        try:
            from homeassistant.config import async_check_ha_config_file
        except ImportError as e:  # pragma: no cover
            raise ToolError(f"check_config unavailable: {e}") from e

    result = await async_check_ha_config_file(hass)
    if isinstance(result, str):
        # Old API returned an error string or None.
        return {"valid": result is None, "error": result}
    return {"valid": True, "result": str(result)}


async def _get_health(hass: HomeAssistant) -> dict[str, Any]:
    try:
        from homeassistant.components import system_health
    except ImportError as e:
        raise ToolError(f"system_health not loaded: {e}") from e

    if not hass.data.get(system_health.DOMAIN):
        return {"domains": {}, "note": "system_health integration not loaded"}

    domains = await system_health.get_info(hass)
    return {"domains": domains}


async def _read_error_log(hass: HomeAssistant, lines: int) -> dict[str, Any]:
    path = hass.config.path("home-assistant.log")
    if not os.path.exists(path):
        return {"path": path, "lines": [], "note": "log file does not exist"}

    def _tail() -> list[str]:
        with open(path, "rb") as f:
            try:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                block = 8192
                data = b""
                while size > 0 and data.count(b"\n") <= lines:
                    step = min(block, size)
                    size -= step
                    f.seek(size)
                    data = f.read(step) + data
                return data.decode("utf-8", errors="replace").splitlines()[-lines:]
            except OSError:
                f.seek(0)
                return f.read().decode("utf-8", errors="replace").splitlines()[-lines:]

    tail = await hass.async_add_executor_job(_tail)
    return {"path": path, "lines": tail, "count": len(tail)}
