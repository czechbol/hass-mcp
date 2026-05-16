"""Event bus tools."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..registry import LIMIT_FIELD, OFFSET_FIELD, paginate, schema, tool


@tool(
    name="ha_list_events",
    description="List event types currently subscribed to, with listener counts.",
    input_schema=schema(
        properties={"limit": LIMIT_FIELD, "offset": OFFSET_FIELD},
    ),
    read_only=True,
)
async def ha_list_events(hass: HomeAssistant, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    listeners = hass.bus.async_listeners()
    items = [{"event_type": k, "listener_count": v} for k, v in sorted(listeners.items())]
    return paginate(items, limit, offset)


@tool(
    name="ha_fire_event",
    description=(
        "Fire an event on the Home Assistant event bus. Gated by the "
        "'allow_fire_event' integration option."
    ),
    input_schema=schema(
        properties={
            "event_type": {"type": "string"},
            "event_data": {"type": "object", "additionalProperties": True},
        },
        required=["event_type"],
    ),
    read_only=False,
    idempotent=False,
    requires_write=True,
    requires_fire_event=True,
)
async def ha_fire_event(
    hass: HomeAssistant,
    event_type: str,
    event_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hass.bus.async_fire(event_type, event_data or {})
    return {"event_type": event_type, "fired": True}
