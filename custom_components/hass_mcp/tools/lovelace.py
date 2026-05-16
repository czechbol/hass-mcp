"""ha_lovelace — read dashboards, resources, configs."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..protocol import ToolError
from ..registry import LIMIT_FIELD, OFFSET_FIELD, paginate, schema, tool
from ..ws import WsCallError, ws_call

_OPS = ("info", "dashboards", "config", "resources")


@tool(
    name="ha_lovelace",
    description=(
        "Read Lovelace dashboards / resources. ops: info (storage mode), "
        "dashboards (list), config (full config for a url_path; null url_path "
        "= default dashboard), resources (extra JS/CSS modules)."
    ),
    input_schema=schema(
        properties={
            "op": {"type": "string", "enum": list(_OPS)},
            "url_path": {
                "type": "string",
                "description": "Dashboard url_path for op=config (omit for default).",
            },
            "limit": LIMIT_FIELD,
            "offset": OFFSET_FIELD,
        },
        required=["op"],
    ),
    read_only=True,
)
async def ha_lovelace(
    hass: HomeAssistant,
    op: str,
    url_path: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if op not in _OPS:
        raise ToolError(f"unknown op '{op}'")

    if op == "info":
        try:
            return await ws_call(hass, "lovelace/info")
        except WsCallError as e:
            raise ToolError(str(e)) from e

    if op == "dashboards":
        try:
            items = await ws_call(hass, "lovelace/dashboards/list")
        except WsCallError as e:
            raise ToolError(str(e)) from e
        return paginate(list(items or []), limit, offset)

    if op == "config":
        payload: dict[str, Any] = {}
        if url_path is not None:
            payload["url_path"] = url_path
        try:
            return await ws_call(hass, "lovelace/config", payload)
        except WsCallError as e:
            raise ToolError(str(e)) from e

    if op == "resources":
        try:
            items = await ws_call(hass, "lovelace/resources")
        except WsCallError as e:
            raise ToolError(str(e)) from e
        return paginate(list(items or []), limit, offset)

    raise ToolError(f"unsupported op '{op}'")
