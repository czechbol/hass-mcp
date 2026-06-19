"""ha_lovelace — dashboards, resources, configs (read + write)."""

from __future__ import annotations

import json
from typing import Any

import orjson
import yaml
from homeassistant.core import HomeAssistant

from ..const import CONF_ALLOW_DESTRUCTIVE, DOMAIN
from ..protocol import ToolError
from ..registry import LIMIT_FIELD, OFFSET_FIELD, paginate, schema, tool
from ..ws import WsCallError, ws_call

_READ_OPS = ("info", "dashboards", "config", "resources")
_WRITE_OPS = (
    "save_config",
    "create_dashboard",
    "update_dashboard",
    "create_resource",
    "update_resource",
)
_DESTRUCTIVE_OPS = ("delete_config", "delete_dashboard", "delete_resource")
_OPS = (*_READ_OPS, *_WRITE_OPS, *_DESTRUCTIVE_OPS)


@tool(
    name="ha_lovelace",
    description=(
        "Lovelace dashboards / resources / configs. "
        "Read ops: info (resource_mode), dashboards (list), config (full "
        "config for url_path; omit url_path = default), resources (extra "
        "JS/CSS modules). "
        "Write ops (require allow_write): save_config (url_path?, config: "
        "dict|str), create_dashboard (data), update_dashboard "
        "(dashboard_id, data), create_resource (data: {res_type,url}), "
        "update_resource (resource_id, data). "
        "Destructive ops (require allow_destructive): delete_config "
        "(url_path?), delete_dashboard (dashboard_id), delete_resource "
        "(resource_id). "
        "Storage-mode only for resource CRUD; YAML-mode dashboards reject "
        "save/delete."
    ),
    input_schema=schema(
        properties={
            "op": {"type": "string", "enum": list(_OPS)},
            "url_path": {
                "type": "string",
                "description": "Dashboard url_path for config/save_config/delete_config (omit for default).",
            },
            "dashboard_id": {
                "type": "string",
                "description": "Storage dashboard id (from dashboards list) for update/delete.",
            },
            "resource_id": {
                "type": "string",
                "description": "Resource id (from resources list) for update/delete.",
            },
            "config": {
                "description": (
                    "Dashboard config for save_config. Either a JSON object or "
                    "a YAML/JSON string (parsed server-side). Must deserialize "
                    "to a mapping with at least one of: views, strategy."
                ),
            },
            "data": {
                "type": "object",
                "additionalProperties": True,
                "description": (
                    "Fields for create_*/update_* ops. Dashboards: "
                    "url_path, title, icon, mode, show_in_sidebar, "
                    "require_admin. Resources: res_type (module/css/js), "
                    "url."
                ),
            },
            "limit": LIMIT_FIELD,
            "offset": OFFSET_FIELD,
        },
        required=["op"],
    ),
    read_only=False,
    requires_write=True,
)
async def ha_lovelace(
    hass: HomeAssistant,
    op: str,
    url_path: str | None = None,
    dashboard_id: str | None = None,
    resource_id: str | None = None,
    config: Any = None,
    data: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if op not in _OPS:
        raise ToolError(f"unknown op '{op}'")

    if op in _DESTRUCTIVE_OPS:
        opts = hass.data.get(DOMAIN, {}).get("options", {})
        if not opts.get(CONF_ALLOW_DESTRUCTIVE, False):
            raise ToolError(
                f"op '{op}' requires allow_destructive=true. Toggle it in "
                "HA → Settings → Devices & Services → Native MCP for Home Assistant → "
                "Configure (not a per-call argument)."
            )

    if op == "info":
        return await _call(hass, "lovelace/info")

    if op == "dashboards":
        items = await _call(hass, "lovelace/dashboards/list")
        return paginate(list(items or []), limit, offset)

    if op == "config":
        payload: dict[str, Any] = {}
        if url_path is not None:
            payload["url_path"] = url_path
        return _materialize(await _call(hass, "lovelace/config", payload))

    if op == "resources":
        items = await _call(hass, "lovelace/resources")
        return paginate(list(items or []), limit, offset)

    if op == "save_config":
        if config is None:
            raise ToolError("op=save_config requires 'config' (dict or YAML/JSON string)")
        config_dict = _coerce_config(config)
        payload = {"config": config_dict}
        if url_path is not None:
            payload["url_path"] = url_path
        return _ok(await _call(hass, "lovelace/config/save", payload))

    if op == "delete_config":
        payload = {}
        if url_path is not None:
            payload["url_path"] = url_path
        return _ok(await _call(hass, "lovelace/config/delete", payload))

    if op == "create_dashboard":
        if not data:
            raise ToolError("op=create_dashboard requires 'data' with url_path, title, mode, …")
        return await _call(hass, "lovelace/dashboards/create", dict(data))

    if op == "update_dashboard":
        if not dashboard_id:
            raise ToolError("op=update_dashboard requires 'dashboard_id'")
        if not data:
            raise ToolError("op=update_dashboard requires 'data' with fields to change")
        payload = {"dashboard_id": dashboard_id, **data}
        return await _call(hass, "lovelace/dashboards/update", payload)

    if op == "delete_dashboard":
        if not dashboard_id:
            raise ToolError("op=delete_dashboard requires 'dashboard_id'")
        return _ok(await _call(hass, "lovelace/dashboards/delete", {"dashboard_id": dashboard_id}))

    if op == "create_resource":
        if not data:
            raise ToolError(
                "op=create_resource requires 'data' with res_type and url "
                "(storage resource_mode only)"
            )
        return await _call(hass, "lovelace/resources/create", dict(data))

    if op == "update_resource":
        if not resource_id:
            raise ToolError("op=update_resource requires 'resource_id'")
        if not data:
            raise ToolError("op=update_resource requires 'data' with fields to change")
        payload = {"resource_id": resource_id, **data}
        return await _call(hass, "lovelace/resources/update", payload)

    if op == "delete_resource":
        if not resource_id:
            raise ToolError("op=delete_resource requires 'resource_id'")
        return _ok(await _call(hass, "lovelace/resources/delete", {"resource_id": resource_id}))

    raise ToolError(f"unsupported op '{op}'")


async def _call(hass: HomeAssistant, cmd: str, payload: dict[str, Any] | None = None) -> Any:
    try:
        return await ws_call(hass, cmd, payload)
    except WsCallError as e:
        raise ToolError(str(e)) from e


def _ok(result: Any) -> dict[str, Any]:
    return {"ok": True, "result": result}


def _coerce_config(config: Any) -> dict[str, Any]:
    """Coerce save_config input to a dict.

    Accepts a dict (returned as-is) or a YAML/JSON string (parsed via
    yaml.safe_load — which also handles JSON). Anything else, or a
    string that parses to a non-dict, raises ToolError so HA doesn't
    persist a malformed payload that would brick the dashboard.
    """
    if isinstance(config, dict):
        return config
    if isinstance(config, str):
        try:
            parsed = yaml.safe_load(config)
        except yaml.YAMLError as e:
            raise ToolError(f"save_config: 'config' string is not valid YAML/JSON: {e}") from e
        if not isinstance(parsed, dict):
            raise ToolError(
                "save_config: 'config' string must deserialize to a mapping "
                f"(got {type(parsed).__name__})"
            )
        return parsed
    raise ToolError(
        f"save_config: 'config' must be dict or YAML/JSON string (got {type(config).__name__})"
    )


def _materialize(value: Any) -> Any:
    """Convert orjson.Fragment (returned by HA's lovelace/config WS) to a dict.

    HA's lovelace handler returns an ``orjson.Fragment`` wrapping pre-encoded
    JSON bytes. Without materialization our JSON encoder falls back to
    ``str(fragment)`` and clients see ``<orjson.Fragment object at 0x...>``.
    """
    if isinstance(value, orjson.Fragment):
        return json.loads(orjson.dumps(value))
    return value
