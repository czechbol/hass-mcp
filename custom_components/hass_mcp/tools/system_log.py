"""ha_system_log — HA's in-memory system log."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..protocol import ToolError
from ..registry import LIMIT_FIELD, OFFSET_FIELD, paginate, schema, tool
from ..ws import WsCallError, ws_call

_OPS = ("list", "clear")


@tool(
    name="ha_system_log",
    description=(
        "Read or clear HA's in-memory system log entries (errors, warnings). "
        "Different from ha_error_log which tails the on-disk log file."
    ),
    input_schema=schema(
        properties={
            "op": {"type": "string", "enum": list(_OPS)},
            "level": {
                "type": "string",
                "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                "description": "Filter for op=list.",
            },
            "logger_prefix": {
                "type": "string",
                "description": "Filter by logger-name prefix for op=list.",
            },
            "limit": LIMIT_FIELD,
            "offset": OFFSET_FIELD,
        },
        required=["op"],
    ),
    read_only=False,
)
async def ha_system_log(
    hass: HomeAssistant,
    op: str,
    level: str | None = None,
    logger_prefix: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if op not in _OPS:
        raise ToolError(f"unknown op '{op}'")

    if op == "list":
        try:
            entries = await ws_call(hass, "system_log/list")
        except WsCallError as e:
            raise ToolError(str(e)) from e
        rows = list(entries or [])
        if level:
            rows = [r for r in rows if r.get("level") == level]
        if logger_prefix:
            rows = [r for r in rows if (r.get("name") or "").startswith(logger_prefix)]
        return paginate(rows, limit, offset)

    if op == "clear":
        try:
            await hass.services.async_call("system_log", "clear", {}, blocking=True)
        except Exception as e:
            raise ToolError(f"clear failed: {e}") from e
        return {"cleared": True}

    raise ToolError(f"unsupported op '{op}'")
