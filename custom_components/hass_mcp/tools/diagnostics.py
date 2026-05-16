"""ha_diagnostics — per-integration / per-device diagnostics dump."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from ..protocol import ToolError
from ..registry import LIMIT_FIELD, OFFSET_FIELD, paginate, schema, tool

_OPS = ("list", "config_entry", "device")


@tool(
    name="ha_diagnostics",
    description=(
        "Inspect integration diagnostics (the data the HA UI's 'Download "
        "diagnostics' button produces). ops: list (integrations that support "
        "diagnostics), config_entry (dump for a config entry), device (dump "
        "for a specific device under a config entry)."
    ),
    input_schema=schema(
        properties={
            "op": {"type": "string", "enum": list(_OPS)},
            "entry_id": {
                "type": "string",
                "description": "config entry id (required for op=config_entry, op=device).",
            },
            "device_id": {
                "type": "string",
                "description": "device id (required for op=device).",
            },
            "limit": LIMIT_FIELD,
            "offset": OFFSET_FIELD,
        },
        required=["op"],
    ),
    read_only=True,
)
async def ha_diagnostics(
    hass: HomeAssistant,
    op: str,
    entry_id: str | None = None,
    device_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if op not in _OPS:
        raise ToolError(f"unknown op '{op}'")

    try:
        from homeassistant.components.diagnostics import (
            DOMAIN as DIAGNOSTICS_DOMAIN,
        )
    except ImportError as e:
        raise ToolError(f"diagnostics integration not loaded: {e}") from e

    data = hass.data.get(DIAGNOSTICS_DOMAIN)
    if data is None:
        raise ToolError("diagnostics not loaded")
    platforms = data.platforms

    if op == "list":
        items = [
            {
                "domain": dom,
                "supports_config_entry_diagnostics": p.config_entry_diagnostics is not None,
                "supports_device_diagnostics": p.device_diagnostics is not None,
            }
            for dom, p in sorted(platforms.items())
        ]
        return paginate(items, limit, offset)

    if not entry_id:
        raise ToolError(f"op={op} requires entry_id")
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        raise ToolError(f"config entry '{entry_id}' not found")

    info = platforms.get(entry.domain)
    if info is None:
        raise ToolError(f"integration '{entry.domain}' does not provide diagnostics")

    if op == "config_entry":
        if info.config_entry_diagnostics is None:
            raise ToolError(f"integration '{entry.domain}' has no config_entry diagnostics")
        try:
            result = await info.config_entry_diagnostics(hass, entry)
        except Exception as e:
            raise ToolError(f"diagnostics failed: {type(e).__name__}: {e}") from e
        return {"domain": entry.domain, "entry_id": entry_id, "data": dict(result)}

    if op == "device":
        if not device_id:
            raise ToolError("op=device requires device_id")
        if info.device_diagnostics is None:
            raise ToolError(f"integration '{entry.domain}' has no device diagnostics")
        device = dr.async_get(hass).async_get(device_id)
        if device is None:
            raise ToolError(f"device '{device_id}' not found")
        try:
            result = await info.device_diagnostics(hass, entry, device)
        except Exception as e:
            raise ToolError(f"diagnostics failed: {type(e).__name__}: {e}") from e
        return {
            "domain": entry.domain,
            "entry_id": entry_id,
            "device_id": device_id,
            "data": dict(result),
        }

    raise ToolError(f"unsupported op '{op}'")
