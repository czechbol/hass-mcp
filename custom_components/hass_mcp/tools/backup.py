"""ha_backup — backup integration ops."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..protocol import ToolError
from ..registry import schema, tool
from ..ws import WsCallError, ws_call

_OPS = (
    "info",
    "details",
    "generate",
    "delete",
    "restore",
    "agents_info",
    "config_info",
)


@tool(
    name="ha_backup",
    description=(
        "Manage Home Assistant backups. ops: info (list), details (single "
        "backup), generate (create new), delete, restore, agents_info "
        "(configured backup storage agents), config_info (automatic-backup "
        "settings)."
    ),
    input_schema=schema(
        properties={
            "op": {"type": "string", "enum": list(_OPS)},
            "backup_id": {"type": "string", "description": "For details/delete/restore."},
            "agent_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Storage agent ids for generate.",
            },
            "name": {"type": "string", "description": "Backup name for generate."},
            "password": {
                "type": "string",
                "description": "Optional password for generate/restore.",
            },
            "include_database": {"type": "boolean", "default": True},
            "include_folders": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Folders to include for generate.",
            },
            "include_addons": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Add-on slugs for generate.",
            },
            "include_all_addons": {"type": "boolean", "default": False},
        },
        required=["op"],
    ),
    read_only=False,
    requires_write=True,
)
async def ha_backup(
    hass: HomeAssistant,
    op: str,
    backup_id: str | None = None,
    agent_ids: list[str] | None = None,
    name: str | None = None,
    password: str | None = None,
    include_database: bool = True,
    include_folders: list[str] | None = None,
    include_addons: list[str] | None = None,
    include_all_addons: bool = False,
) -> dict[str, Any]:
    if op not in _OPS:
        raise ToolError(f"unknown op '{op}'")

    cmd_map = {
        "info": ("backup/info", None),
        "agents_info": ("backup/agents/info", None),
        "config_info": ("backup/config/info", None),
    }
    if op in cmd_map:
        cmd, _ = cmd_map[op]
        try:
            return await ws_call(hass, cmd)
        except WsCallError as e:
            raise ToolError(str(e)) from e

    if op == "details":
        if not backup_id:
            raise ToolError("op=details requires backup_id")
        try:
            return await ws_call(hass, "backup/details", {"backup_id": backup_id})
        except WsCallError as e:
            raise ToolError(str(e)) from e

    if op == "delete":
        if not backup_id:
            raise ToolError("op=delete requires backup_id")
        try:
            await ws_call(hass, "backup/delete", {"backup_id": backup_id})
        except WsCallError as e:
            raise ToolError(str(e)) from e
        return {"backup_id": backup_id, "deleted": True}

    if op == "generate":
        if not agent_ids:
            raise ToolError("op=generate requires agent_ids (see op=agents_info)")
        payload: dict[str, Any] = {
            "agent_ids": agent_ids,
            "include_database": include_database,
            "include_all_addons": include_all_addons,
        }
        if name:
            payload["name"] = name
        if password:
            payload["password"] = password
        if include_folders:
            payload["include_folders"] = include_folders
        if include_addons:
            payload["include_addons"] = include_addons
        try:
            return await ws_call(hass, "backup/generate", payload, timeout=120)
        except WsCallError as e:
            raise ToolError(str(e)) from e

    if op == "restore":
        if not backup_id:
            raise ToolError("op=restore requires backup_id")
        payload = {"backup_id": backup_id}
        if agent_ids:
            payload["agent_id"] = agent_ids[0]
        if password:
            payload["password"] = password
        try:
            return await ws_call(hass, "backup/restore", payload, timeout=600)
        except WsCallError as e:
            raise ToolError(str(e)) from e

    raise ToolError(f"unsupported op '{op}'")
