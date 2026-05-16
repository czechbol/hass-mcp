"""ha_validate_config — validate trigger/condition/action blocks."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..protocol import ToolError
from ..registry import schema, tool


@tool(
    name="ha_validate_config",
    description=(
        "Validate trigger/condition/action configuration blocks against HA's "
        "schemas. Useful before writing an automation/script via "
        "ha_yaml_config. Returns per-kind validation results."
    ),
    input_schema=schema(
        properties={
            "triggers": {
                "type": "array",
                "items": {"type": "object", "additionalProperties": True},
            },
            "conditions": {
                "type": "array",
                "items": {"type": "object", "additionalProperties": True},
            },
            "actions": {
                "type": "array",
                "items": {"type": "object", "additionalProperties": True},
            },
        }
    ),
    read_only=True,
)
async def ha_validate_config(
    hass: HomeAssistant,
    triggers: list[dict[str, Any]] | None = None,
    conditions: list[dict[str, Any]] | None = None,
    actions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {}

    if triggers:
        from homeassistant.helpers import trigger

        try:
            validated = await trigger.async_validate_trigger_config(hass, triggers)
            out["triggers"] = {"valid": True, "count": len(validated)}
        except Exception as e:  # noqa: BLE001
            out["triggers"] = {"valid": False, "error": f"{type(e).__name__}: {e}"}

    if conditions:
        from homeassistant.helpers import condition

        results: list[dict[str, Any]] = []
        all_ok = True
        for i, c in enumerate(conditions):
            try:
                await condition.async_validate_condition_config(hass, c)
                results.append({"index": i, "valid": True})
            except Exception as e:  # noqa: BLE001
                all_ok = False
                results.append({"index": i, "valid": False, "error": f"{type(e).__name__}: {e}"})
        out["conditions"] = {"valid": all_ok, "results": results}

    if actions:
        from homeassistant.helpers import script

        try:
            await script.async_validate_actions_config(hass, actions)
            out["actions"] = {"valid": True, "count": len(actions)}
        except Exception as e:  # noqa: BLE001
            out["actions"] = {"valid": False, "error": f"{type(e).__name__}: {e}"}

    if not out:
        raise ToolError("provide at least one of: triggers, conditions, actions")
    return out
