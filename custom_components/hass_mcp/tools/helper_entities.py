"""ha_helper — CRUD for input_*, counter, timer, schedule helpers."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..protocol import ToolError
from ..registry import LIMIT_FIELD, OFFSET_FIELD, paginate, schema, tool
from ..ws import WsCallError, ws_call

_KINDS = (
    "input_boolean",
    "input_number",
    "input_select",
    "input_text",
    "input_datetime",
    "counter",
    "timer",
    "schedule",
)
_OPS = ("list", "create", "update", "delete")


@tool(
    name="ha_helper",
    description=(
        "Manage helper entities (input_boolean / input_number / input_select / "
        "input_text / input_datetime / counter / timer / schedule). For "
        "value mutations (set_value, turn_on, increment, etc.) use "
        "ha_call_service. This tool is for adding/removing helpers."
    ),
    input_schema=schema(
        properties={
            "kind": {"type": "string", "enum": list(_KINDS)},
            "op": {"type": "string", "enum": list(_OPS)},
            "id": {
                "type": "string",
                "description": "Helper id (for op=update / op=delete). Found in op=list.",
            },
            "config": {
                "type": "object",
                "additionalProperties": True,
                "description": "Config payload for op=create / op=update. Must include 'name' for create. See HA docs for kind-specific fields.",
            },
            "limit": LIMIT_FIELD,
            "offset": OFFSET_FIELD,
        },
        required=["kind", "op"],
    ),
    read_only=False,
    idempotent=False,
    requires_write=True,
)
async def ha_helper(
    hass: HomeAssistant,
    kind: str,
    op: str,
    id: str | None = None,
    config: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if kind not in _KINDS:
        raise ToolError(f"unknown kind '{kind}'")
    if op not in _OPS:
        raise ToolError(f"unknown op '{op}'")

    if op == "list":
        try:
            items = await ws_call(hass, f"{kind}/list")
        except WsCallError as e:
            raise ToolError(str(e)) from e
        return paginate(list(items or []), limit, offset)

    if op == "create":
        if not config or not config.get("name"):
            raise ToolError("op=create requires config with at least 'name'")
        try:
            result = await ws_call(hass, f"{kind}/create", config)
        except WsCallError as e:
            raise ToolError(str(e)) from e
        return {"created": True, "item": result}

    if op == "update":
        if not id:
            raise ToolError("op=update requires id")
        if not config:
            raise ToolError("op=update requires config")
        try:
            result = await ws_call(hass, f"{kind}/update", {f"{kind}_id": id, **config})
        except WsCallError as e:
            raise ToolError(str(e)) from e
        return {"updated": True, "item": result}

    if op == "delete":
        if not id:
            raise ToolError("op=delete requires id")
        try:
            await ws_call(hass, f"{kind}/delete", {f"{kind}_id": id})
        except WsCallError as e:
            raise ToolError(str(e)) from e
        return {"deleted": True, "id": id}

    raise ToolError(f"unsupported op '{op}'")
