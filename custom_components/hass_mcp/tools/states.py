"""State-machine tools."""

from __future__ import annotations

import fnmatch
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
)
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers import (
    entity_registry as er,
)

from ..protocol import ToolError
from ..registry import (
    LIMIT_FIELD,
    OFFSET_FIELD,
    paginate,
    schema,
    tool,
)


def _state_to_dict(state) -> dict[str, Any]:
    return {
        "entity_id": state.entity_id,
        "state": state.state,
        "attributes": dict(state.attributes),
        "last_changed": state.last_changed.isoformat() if state.last_changed else None,
        "last_updated": state.last_updated.isoformat() if state.last_updated else None,
    }


@tool(
    name="ha_list_states",
    description=(
        "List entity states with optional filters. Filters compose with AND. "
        "Use this to discover entities before calling other tools."
    ),
    input_schema=schema(
        properties={
            "domain": {
                "type": "string",
                "description": "Filter by entity domain (e.g. 'light', 'sensor').",
            },
            "entity_pattern": {
                "type": "string",
                "description": "fnmatch-style glob applied to entity_id (e.g. 'light.kitchen_*').",
            },
            "area": {
                "type": "string",
                "description": "Area id or area name (case-insensitive).",
            },
            "device_id": {"type": "string"},
            "label": {"type": "string", "description": "Label id or name."},
            "include_attributes": {
                "type": "boolean",
                "default": False,
                "description": "If true, include the full attributes object per entity. Default false to keep responses small; use ha_get_state for full attrs on a specific entity.",
            },
            "limit": LIMIT_FIELD,
            "offset": OFFSET_FIELD,
        }
    ),
    read_only=True,
)
async def ha_list_states(
    hass: HomeAssistant,
    domain: str | None = None,
    entity_pattern: str | None = None,
    area: str | None = None,
    device_id: str | None = None,
    label: str | None = None,
    include_attributes: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    states = hass.states.async_all()

    area_id_filter: str | None = None
    if area:
        ar_reg = ar.async_get(hass)
        a = ar_reg.async_get_area(area) or ar_reg.async_get_area_by_name(area)
        if a is None:
            raise ToolError(f"area '{area}' not found; check ha_registry kind=area op=list")
        area_id_filter = a.id

    label_id_filter: str | None = None
    if label:
        from homeassistant.helpers import label_registry as lr

        lr_reg = lr.async_get(hass)
        lab = lr_reg.async_get_label(label)
        if lab is None:
            for cand in lr_reg.async_list_labels():
                if cand.name.lower() == label.lower():
                    lab = cand
                    break
        if lab is None:
            raise ToolError(f"label '{label}' not found; check ha_registry kind=label op=list")
        label_id_filter = lab.label_id

    needs_registry = bool(area_id_filter or device_id or label_id_filter)
    er_reg = er.async_get(hass) if needs_registry else None
    dr_reg = dr.async_get(hass) if (needs_registry and area_id_filter) else None

    def keep(state) -> bool:
        if domain and state.domain != domain:
            return False
        if entity_pattern and not fnmatch.fnmatchcase(state.entity_id, entity_pattern):
            return False
        if not needs_registry:
            return True
        entry = er_reg.async_get(state.entity_id) if er_reg else None
        if device_id and (not entry or entry.device_id != device_id):
            return False
        if label_id_filter and (not entry or label_id_filter not in (entry.labels or set())):
            return False
        if area_id_filter:
            entry_area = entry.area_id if entry else None
            if not entry_area and entry and entry.device_id and dr_reg:
                dev = dr_reg.async_get(entry.device_id)
                entry_area = dev.area_id if dev else None
            if entry_area != area_id_filter:
                return False
        return True

    filtered = [s for s in states if keep(s)]
    items = [_state_to_dict(s) for s in filtered]
    if not include_attributes:
        for it, s in zip(items, filtered, strict=False):
            fn = s.attributes.get("friendly_name") if s.attributes else None
            it.pop("attributes", None)
            if fn:
                it["friendly_name"] = fn
    return paginate(items, limit, offset)


@tool(
    name="ha_get_state",
    description="Get full state and attributes for a single entity.",
    input_schema=schema(
        properties={"entity_id": {"type": "string"}},
        required=["entity_id"],
    ),
    read_only=True,
)
async def ha_get_state(hass: HomeAssistant, entity_id: str) -> dict[str, Any]:
    s = hass.states.get(entity_id)
    if s is None:
        raise ToolError(f"entity_id '{entity_id}' not found")
    return _state_to_dict(s)


@tool(
    name="ha_set_state",
    description=(
        "Set a state on the state machine without invoking a device. Useful for "
        "MQTT-style virtual sensors or to override an entity's reported state. "
        "Does NOT command physical devices — use ha_call_service for that."
    ),
    input_schema=schema(
        properties={
            "entity_id": {"type": "string"},
            "state": {"type": "string"},
            "attributes": {"type": "object", "additionalProperties": True},
            "force_update": {"type": "boolean", "default": False},
        },
        required=["entity_id", "state"],
    ),
    read_only=False,
    destructive=False,
    idempotent=False,
    requires_write=True,
)
async def ha_set_state(
    hass: HomeAssistant,
    entity_id: str,
    state: str,
    attributes: dict[str, Any] | None = None,
    force_update: bool = False,
) -> dict[str, Any]:
    hass.states.async_set(entity_id, state, attributes or {}, force_update=force_update)
    s = hass.states.get(entity_id)
    return _state_to_dict(s) if s else {"entity_id": entity_id, "state": state}


@tool(
    name="ha_delete_state",
    description=(
        "Remove an entity from the state machine. Does not delete it from the "
        "entity registry (use ha_registry kind=entity op=delete for that)."
    ),
    input_schema=schema(
        properties={"entity_id": {"type": "string"}},
        required=["entity_id"],
    ),
    read_only=False,
    destructive=True,
    idempotent=True,
    requires_write=True,
    requires_destructive=True,
)
async def ha_delete_state(hass: HomeAssistant, entity_id: str) -> dict[str, Any]:
    removed = hass.states.async_remove(entity_id)
    return {"entity_id": entity_id, "removed": bool(removed)}
