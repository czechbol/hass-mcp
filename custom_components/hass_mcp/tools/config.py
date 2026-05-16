"""Core config / health / log tools."""

from __future__ import annotations

import os
from typing import Any

from homeassistant.core import HomeAssistant

from ..protocol import ToolError
from ..registry import schema, tool


@tool(
    name="ha_get_config",
    description="Return Home Assistant core configuration (version, location, components, URLs, unit_system).",
    input_schema=schema(),
    read_only=True,
)
async def ha_get_config(hass: HomeAssistant) -> dict[str, Any]:
    return hass.config.as_dict()


@tool(
    name="ha_check_config",
    description="Validate configuration.yaml. Reports errors and warnings without restarting HA.",
    input_schema=schema(),
    read_only=True,
)
async def ha_check_config(hass: HomeAssistant) -> dict[str, Any]:
    try:
        from homeassistant.components.config.core import (
            async_check_ha_config_file,
        )
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


@tool(
    name="ha_get_system_health",
    description="Aggregate system_health info from all registered integrations.",
    input_schema=schema(),
    read_only=True,
)
async def ha_get_system_health(hass: HomeAssistant) -> dict[str, Any]:
    try:
        from homeassistant.components import system_health
    except ImportError as e:
        raise ToolError(f"system_health not loaded: {e}") from e

    if not hass.data.get(system_health.DOMAIN):
        return {"domains": {}, "note": "system_health integration not loaded"}

    domains = await system_health.get_info(hass)
    return {"domains": domains}


@tool(
    name="ha_error_log",
    description="Return the last N lines from the Home Assistant error log file.",
    input_schema=schema(
        properties={
            "lines": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5000,
                "default": 200,
            },
        }
    ),
    read_only=True,
)
async def ha_error_log(hass: HomeAssistant, lines: int = 200) -> dict[str, Any]:
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
