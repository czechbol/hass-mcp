"""ha_recorder — info + purge ops."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..protocol import ToolError
from ..registry import schema, tool

_OPS = ("info", "purge", "purge_entities")


@tool(
    name="ha_recorder",
    description=(
        "Recorder ops: info (db size, oldest run), purge (delete data older "
        "than N days), purge_entities (delete data for specific entity_ids)."
    ),
    input_schema=schema(
        properties={
            "op": {"type": "string", "enum": list(_OPS)},
            "keep_days": {
                "type": "integer",
                "minimum": 0,
                "description": "For op=purge: keep last N days (0 = purge everything).",
            },
            "repack": {
                "type": "boolean",
                "default": False,
                "description": "For op=purge: shrink SQLite database after purge.",
            },
            "apply_filter": {
                "type": "boolean",
                "default": False,
                "description": "For op=purge: also apply the recorder include/exclude filter to existing data.",
            },
            "entity_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "For op=purge_entities.",
            },
            "domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "For op=purge_entities: also purge all entities in these domains.",
            },
            "entity_globs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "For op=purge_entities: glob patterns.",
            },
        },
        required=["op"],
    ),
    read_only=False,
    destructive=True,
    requires_write=True,
    requires_destructive=True,
)
async def ha_recorder(
    hass: HomeAssistant,
    op: str,
    keep_days: int | None = None,
    repack: bool = False,
    apply_filter: bool = False,
    entity_ids: list[str] | None = None,
    domains: list[str] | None = None,
    entity_globs: list[str] | None = None,
) -> dict[str, Any]:
    if op not in _OPS:
        raise ToolError(f"unknown op '{op}'")

    try:
        from homeassistant.components.recorder import get_instance
    except ImportError as e:
        raise ToolError(f"recorder not loaded: {e}") from e

    instance = get_instance(hass)

    if op == "info":
        return {
            "db_url": str(instance.db_url).split("://", 1)[0] + "://***",
            "engine": instance.engine.dialect.name if instance.engine else None,
            "max_entity_history": getattr(instance, "max_entity_history", None),
            "recording": instance.recording,
            "auto_purge": instance.auto_purge,
            "auto_repack": instance.auto_repack,
            "keep_days": instance.keep_days,
        }

    # Purge ops go through service calls to ensure proper queueing.
    if op == "purge":
        data: dict[str, Any] = {"repack": repack, "apply_filter": apply_filter}
        if keep_days is not None:
            data["keep_days"] = keep_days
        await hass.services.async_call("recorder", "purge", data, blocking=True)
        return {"queued": True, **data}

    if op == "purge_entities":
        if not (entity_ids or domains or entity_globs):
            raise ToolError(
                "op=purge_entities requires at least one of entity_ids, domains, entity_globs"
            )
        data = {}
        if entity_ids:
            data["entity_id"] = entity_ids
        if domains:
            data["domains"] = domains
        if entity_globs:
            data["entity_globs"] = entity_globs
        await hass.services.async_call("recorder", "purge_entities", data, blocking=True)
        return {"queued": True, **data}

    raise ToolError(f"unsupported op '{op}'")


# Avoid unused-import warnings.
_ = (timedelta, dt_util)
