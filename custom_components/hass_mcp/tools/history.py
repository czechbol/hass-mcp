"""Recorder history tool."""

from __future__ import annotations

from datetime import datetime
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
        "Significant state changes between two timestamps for the listed entities. "
        "Times are ISO 8601 (assume UTC if no offset). Defaults: end=now, start=24h ago."
    ),
    input_schema=schema(
        properties={
            "entity_ids": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "start": {"type": "string", "description": "ISO 8601 start time."},
            "end": {"type": "string", "description": "ISO 8601 end time."},
            "minimal_response": {"type": "boolean", "default": True},
            "no_attributes": {"type": "boolean", "default": False},
            "significant_changes_only": {"type": "boolean", "default": True},
        },
        required=["entity_ids"],
    ),
    read_only=True,
)
async def ha_history(
    hass: HomeAssistant,
    entity_ids: list[str],
    start: str | None = None,
    end: str | None = None,
    minimal_response: bool = True,
    no_attributes: bool = False,
    significant_changes_only: bool = True,
) -> dict[str, Any]:
    try:
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder import history as rec_history
    except ImportError as e:
        raise ToolError(f"recorder not loaded: {e}") from e

    from datetime import timedelta

    start_dt = _parse_dt(start) or (dt_util.utcnow() - timedelta(days=1))
    end_dt = _parse_dt(end) or dt_util.utcnow()

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


def _state_row(s) -> dict[str, Any]:
    if isinstance(s, dict):
        return s
    return {
        "state": getattr(s, "state", None),
        "last_changed": getattr(s, "last_changed", None) and s.last_changed.isoformat(),
        "last_updated": getattr(s, "last_updated", None) and s.last_updated.isoformat(),
        "attributes": dict(getattr(s, "attributes", {}) or {}),
    }
