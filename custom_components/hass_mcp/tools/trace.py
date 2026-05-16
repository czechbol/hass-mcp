"""ha_trace — read automation/script execution traces."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..protocol import ToolError
from ..registry import LIMIT_FIELD, OFFSET_FIELD, paginate, schema, tool

_OPS = ("list", "get", "contexts")
_DOMAINS = ("automation", "script")


@tool(
    name="ha_trace",
    description=(
        "Inspect automation/script execution traces. ops: list (summaries), "
        "get (full trace by run_id), contexts (recent run contexts). Use this "
        "to debug a failing automation — find the run_id from list, then get "
        "the full step-by-step trace."
    ),
    input_schema=schema(
        properties={
            "op": {"type": "string", "enum": list(_OPS)},
            "domain": {
                "type": "string",
                "enum": list(_DOMAINS),
                "description": "automation or script. Required for op=list and op=get.",
            },
            "item_id": {
                "type": "string",
                "description": "Item id (automation/script entry id, e.g. 'hass_mcp_test_auto'). For op=get, required.",
            },
            "run_id": {"type": "string", "description": "Run id for op=get."},
            "limit": LIMIT_FIELD,
            "offset": OFFSET_FIELD,
        },
        required=["op"],
    ),
    read_only=True,
)
async def ha_trace(
    hass: HomeAssistant,
    op: str,
    domain: str | None = None,
    item_id: str | None = None,
    run_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if op not in _OPS:
        raise ToolError(f"unknown op '{op}'")

    try:
        from homeassistant.components.trace.util import (
            async_get_trace,
            async_list_contexts,
            async_list_traces,
        )
    except ImportError as e:
        raise ToolError(f"trace integration not loaded: {e}") from e

    if op == "list":
        if domain not in _DOMAINS:
            raise ToolError("op=list requires domain (automation|script)")
        key = f"{domain}.{item_id}" if item_id else None
        try:
            traces = await async_list_traces(hass, domain, key)
        except Exception as e:
            raise ToolError(f"trace list failed: {e}") from e
        return paginate(list(traces), limit, offset)

    if op == "get":
        if domain not in _DOMAINS or not item_id or not run_id:
            raise ToolError("op=get requires domain, item_id, run_id")
        key = f"{domain}.{item_id}"
        try:
            trace = await async_get_trace(hass, key, run_id)
        except KeyError as e:
            raise ToolError(f"trace not found: {key} run_id={run_id}") from e
        return trace

    if op == "contexts":
        key = f"{domain}.{item_id}" if (domain and item_id) else None
        try:
            contexts = await async_list_contexts(hass, key)
        except Exception as e:
            raise ToolError(f"trace contexts failed: {e}") from e
        return {"contexts": contexts}

    raise ToolError(f"unsupported op '{op}'")
