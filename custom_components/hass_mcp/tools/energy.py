"""ha_energy — energy dashboard preferences."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..protocol import ToolError
from ..registry import schema, tool

_OPS = ("get_prefs", "save_prefs", "validate")


@tool(
    name="ha_energy",
    description=(
        "Energy dashboard preferences. ops: get_prefs (current config), "
        "save_prefs (replace with provided), validate (check existing prefs "
        "against current entities)."
    ),
    input_schema=schema(
        properties={
            "op": {"type": "string", "enum": list(_OPS)},
            "prefs": {
                "type": "object",
                "additionalProperties": True,
                "description": "For op=save_prefs: full energy preferences object (see HA developer docs).",
            },
        },
        required=["op"],
    ),
    read_only=False,
)
async def ha_energy(
    hass: HomeAssistant,
    op: str,
    prefs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if op not in _OPS:
        raise ToolError(f"unknown op '{op}'")

    try:
        from homeassistant.components.energy import data as energy_data
        from homeassistant.components.energy import validate as energy_validate
    except ImportError as e:
        raise ToolError(f"energy integration not loaded: {e}") from e

    manager = await energy_data.async_get_manager(hass)

    if op == "get_prefs":
        return manager.data or {}

    if op == "save_prefs":
        if not prefs:
            raise ToolError("op=save_prefs requires 'prefs'")
        try:
            await manager.async_update(prefs)
        except Exception as e:
            raise ToolError(f"save failed: {e}") from e
        return manager.data or {}

    if op == "validate":
        try:
            result = await energy_validate.async_validate(hass)
        except Exception as e:
            raise ToolError(f"validation failed: {e}") from e
        return {"result": result.as_dict() if hasattr(result, "as_dict") else result}

    raise ToolError(f"unsupported op '{op}'")
