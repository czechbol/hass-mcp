"""ha_hacs — drive HACS install/update/refresh operations."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..protocol import ToolError
from ..registry import LIMIT_FIELD, OFFSET_FIELD, paginate, schema, tool
from ..ws import WsCallError, ws_call

_OPS = (
    "info",
    "list",
    "repository_info",
    "refresh",
    "download",
    "release_notes",
)


@tool(
    name="ha_hacs",
    description=(
        "Drive HACS (Home Assistant Community Store). ops: info (HACS state), "
        "list (all tracked repos), repository_info (one repo), refresh (fetch "
        "latest version info from upstream), download (install a version), "
        "release_notes. Repository id is HACS's internal id (use op=list to "
        "find)."
    ),
    input_schema=schema(
        properties={
            "op": {"type": "string", "enum": list(_OPS)},
            "repository": {"type": "string", "description": "HACS repository id."},
            "version": {
                "type": "string",
                "description": "For op=download: target version/tag (omit for latest).",
            },
            "name_contains": {
                "type": "string",
                "description": "Filter for op=list (case-insensitive substring of repo full_name or display name).",
            },
            "limit": LIMIT_FIELD,
            "offset": OFFSET_FIELD,
        },
        required=["op"],
    ),
    read_only=False,
    requires_write=True,
)
async def ha_hacs(
    hass: HomeAssistant,
    op: str,
    repository: str | None = None,
    version: str | None = None,
    name_contains: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if op not in _OPS:
        raise ToolError(f"unknown op '{op}'")

    if op == "info":
        try:
            return await ws_call(hass, "hacs/info")
        except WsCallError as e:
            raise ToolError(str(e)) from e

    if op == "list":
        try:
            items = await ws_call(hass, "hacs/repositories/list")
        except WsCallError as e:
            raise ToolError(str(e)) from e
        rows = list(items or [])
        if name_contains:
            needle = name_contains.lower()
            rows = [
                r
                for r in rows
                if needle in (str(r.get("full_name", "")).lower())
                or needle in (str(r.get("name", "")).lower())
            ]
        return paginate(rows, limit, offset)

    if not repository:
        raise ToolError(f"op={op} requires 'repository'")

    if op == "repository_info":
        # HACS inconsistency: this command uses 'repository_id' not 'repository'.
        try:
            return await ws_call(hass, "hacs/repository/info", {"repository_id": repository})
        except WsCallError as e:
            raise ToolError(str(e)) from e

    if op == "refresh":
        try:
            await ws_call(hass, "hacs/repository/refresh", {"repository": repository})
        except WsCallError as e:
            raise ToolError(str(e)) from e
        return {"repository": repository, "refreshed": True}

    if op == "download":
        payload: dict[str, Any] = {"repository": repository}
        if version:
            payload["version"] = version
        try:
            await ws_call(hass, "hacs/repository/download", payload, timeout=120)
        except WsCallError as e:
            raise ToolError(str(e)) from e
        return {"repository": repository, "version": version, "downloaded": True}

    if op == "release_notes":
        try:
            return await ws_call(hass, "hacs/repository/release_notes", {"repository": repository})
        except WsCallError as e:
            raise ToolError(str(e)) from e

    raise ToolError(f"unsupported op '{op}'")
