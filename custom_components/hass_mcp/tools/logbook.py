"""Logbook events tool."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..protocol import ToolError
from ..registry import schema, tool


@tool(
    name="ha_logbook",
    description=(
        "Logbook events between two timestamps, optionally filtered to entities. "
        "Defaults: end=now, start=24h ago."
    ),
    input_schema=schema(
        properties={
            "entity_ids": {"type": "array", "items": {"type": "string"}},
            "device_ids": {"type": "array", "items": {"type": "string"}},
            "start": {"type": "string"},
            "end": {"type": "string"},
            "context_id": {"type": "string"},
        }
    ),
    read_only=True,
)
async def ha_logbook(
    hass: HomeAssistant,
    entity_ids: list[str] | None = None,
    device_ids: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    context_id: str | None = None,
) -> dict[str, Any]:
    try:
        from homeassistant.components.logbook.helpers import (
            async_determine_event_types,
            async_filter_entities,
        )
        from homeassistant.components.logbook.processor import EventProcessor
        from homeassistant.components.recorder import get_instance
    except ImportError as e:
        raise ToolError(f"logbook integration not loaded: {e}") from e

    start_dt = dt_util.parse_datetime(start) if start else dt_util.utcnow() - timedelta(days=1)
    if start_dt is None:
        raise ToolError(f"could not parse start '{start}'")
    end_dt = dt_util.parse_datetime(end) if end else dt_util.utcnow()
    if end_dt is None:
        raise ToolError(f"could not parse end '{end}'")
    start_utc = dt_util.as_utc(start_dt)
    end_utc = dt_util.as_utc(end_dt)

    filtered_entity_ids = entity_ids
    if entity_ids:
        try:
            filtered_entity_ids = async_filter_entities(hass, entity_ids)
        except Exception:  # noqa: BLE001 - filter is best-effort
            filtered_entity_ids = entity_ids
        if not filtered_entity_ids and not device_ids:
            return {
                "start": start_utc.isoformat(),
                "end": end_utc.isoformat(),
                "events": [],
            }

    event_types = async_determine_event_types(hass, filtered_entity_ids, device_ids)
    processor = EventProcessor(
        hass,
        event_types,
        entity_ids=filtered_entity_ids,
        device_ids=device_ids,
        context_id=context_id,
        timestamp=True,
        include_entity_name=True,
    )

    events = await get_instance(hass).async_add_executor_job(
        processor.get_events, start_utc, end_utc
    )
    return {
        "start": start_utc.isoformat(),
        "end": end_utc.isoformat(),
        "events": events,
    }
