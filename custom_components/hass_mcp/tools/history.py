"""Recorder timeline tool: state-change history and logbook events."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..protocol import ToolError
from ..registry import schema, tool


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = dt_util.parse_datetime(value)
    if parsed is None:
        raise ToolError(f"could not parse datetime '{value}'; use ISO 8601")
    return dt_util.as_utc(parsed)


@tool(
    name="ha_history",
    description=(
        "Recorder timeline between two timestamps. kind=state_changes returns "
        "significant state changes for the given entities (entity_ids required); "
        "kind=logbook returns human-readable logbook events, optionally filtered "
        "to entities/devices. Times are ISO 8601 (assume UTC if no offset). "
        "Defaults: end=now, start=24h ago."
    ),
    input_schema=schema(
        properties={
            "kind": {"type": "string", "enum": ["state_changes", "logbook"]},
            "entity_ids": {"type": "array", "items": {"type": "string"}},
            "device_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "kind=logbook only.",
            },
            "start": {"type": "string"},
            "end": {"type": "string"},
            "minimal_response": {
                "type": "boolean",
                "default": True,
                "description": "kind=state_changes only.",
            },
            "no_attributes": {
                "type": "boolean",
                "default": False,
                "description": "kind=state_changes only.",
            },
            "significant_changes_only": {
                "type": "boolean",
                "default": True,
                "description": "kind=state_changes only.",
            },
            "context_id": {"type": "string", "description": "kind=logbook only."},
        },
        required=["kind"],
    ),
    read_only=True,
)
async def ha_history(
    hass: HomeAssistant,
    kind: str,
    entity_ids: list[str] | None = None,
    device_ids: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    minimal_response: bool = True,
    no_attributes: bool = False,
    significant_changes_only: bool = True,
    context_id: str | None = None,
) -> dict[str, Any]:
    start_dt = _parse_dt(start) or (dt_util.utcnow() - timedelta(days=1))
    end_dt = _parse_dt(end) or dt_util.utcnow()

    if kind == "state_changes":
        return await _state_changes(
            hass,
            entity_ids,
            start_dt,
            end_dt,
            minimal_response,
            no_attributes,
            significant_changes_only,
        )
    if kind == "logbook":
        return await _logbook(hass, entity_ids, device_ids, start_dt, end_dt, context_id)
    raise ToolError(f"unknown kind '{kind}'; use 'state_changes' or 'logbook'")


async def _state_changes(
    hass: HomeAssistant,
    entity_ids: list[str] | None,
    start_dt: datetime,
    end_dt: datetime,
    minimal_response: bool,
    no_attributes: bool,
    significant_changes_only: bool,
) -> dict[str, Any]:
    if not entity_ids:
        raise ToolError("kind=state_changes requires entity_ids")
    try:
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder import history as rec_history
    except ImportError as e:
        raise ToolError(f"recorder not loaded: {e}") from e

    def _fetch():
        return rec_history.get_significant_states(
            hass,
            start_dt,
            end_dt,
            entity_ids=entity_ids,
            include_start_time_state=True,
            significant_changes_only=significant_changes_only,
            minimal_response=minimal_response,
            no_attributes=no_attributes,
        )

    instance = get_instance(hass)
    raw = await instance.async_add_executor_job(_fetch)

    out: dict[str, list[dict[str, Any]]] = {}
    for entity_id, states in raw.items():
        out[entity_id] = [_state_row(s) for s in states]
    return {"entities": out, "start": start_dt.isoformat(), "end": end_dt.isoformat()}


async def _logbook(
    hass: HomeAssistant,
    entity_ids: list[str] | None,
    device_ids: list[str] | None,
    start_dt: datetime,
    end_dt: datetime,
    context_id: str | None,
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

    filtered_entity_ids = entity_ids
    if entity_ids:
        try:
            filtered_entity_ids = async_filter_entities(hass, entity_ids)
        except Exception:  # noqa: BLE001 - filter is best-effort
            filtered_entity_ids = entity_ids
        if not filtered_entity_ids and not device_ids:
            return {"start": start_dt.isoformat(), "end": end_dt.isoformat(), "events": []}

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

    events = await get_instance(hass).async_add_executor_job(processor.get_events, start_dt, end_dt)
    return {"start": start_dt.isoformat(), "end": end_dt.isoformat(), "events": events}


def _state_row(s) -> dict[str, Any]:
    if isinstance(s, dict):
        return s
    return {
        "state": getattr(s, "state", None),
        "last_changed": getattr(s, "last_changed", None) and s.last_changed.isoformat(),
        "last_updated": getattr(s, "last_updated", None) and s.last_updated.isoformat(),
        "attributes": dict(getattr(s, "attributes", {}) or {}),
    }
