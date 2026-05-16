"""ha_yaml_config — CRUD for automations.yaml / scripts.yaml / scenes.yaml."""

from __future__ import annotations

import secrets
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from ..protocol import ToolError
from ..registry import LIMIT_FIELD, OFFSET_FIELD, paginate, schema, tool

# kind → (filename, structure, reload-service-domain)
_KINDS: dict[str, tuple[str, str, str]] = {
    "automation": ("automations.yaml", "list", "automation"),
    "script": ("scripts.yaml", "dict", "script"),
    "scene": ("scenes.yaml", "list", "scene"),
}
_OPS = ("list", "get", "create", "update", "delete", "reload")


@tool(
    name="ha_yaml_config",
    description=(
        "CRUD for automations.yaml / scripts.yaml / scenes.yaml. Reloads "
        "after mutation. Use ha_validate_config to sanity-check trigger / "
        "condition / action blocks before create/update."
    ),
    input_schema=schema(
        properties={
            "kind": {"type": "string", "enum": list(_KINDS)},
            "op": {"type": "string", "enum": list(_OPS)},
            "id": {
                "type": "string",
                "description": "Identifier. Automation/scene: their 'id' field. Script: the script key (e.g. 'my_script').",
            },
            "config": {
                "type": "object",
                "additionalProperties": True,
                "description": "Full entry config for create/update. See HA docs for required fields per kind.",
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
async def ha_yaml_config(
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

    filename, structure, reload_domain = _KINDS[kind]
    path = hass.config.path(filename)

    data = await _load(hass, path, structure)

    if op == "list":
        items = _to_list(data, structure)
        return paginate(items, limit, offset)

    if op == "get":
        if not id:
            raise ToolError("op=get requires id")
        item = _find(data, structure, id)
        if item is None:
            raise ToolError(f"{kind} '{id}' not found in {filename}")
        return item

    if op == "create":
        if not config:
            raise ToolError("op=create requires config")
        new_id = id or config.get("id") or secrets.token_hex(8)
        if structure == "list":
            entry = {"id": new_id, **{k: v for k, v in config.items() if k != "id"}}
            data.append(entry)
        else:  # dict (script)
            data[new_id] = config
        await _save(hass, path, data, structure)
        await _reload(hass, reload_domain)
        entity_id = _derive_entity_id(reload_domain, structure, new_id, config)
        return {"id": new_id, "entity_id": entity_id, "created": True}

    if op == "update":
        if not id:
            raise ToolError("op=update requires id")
        if not config:
            raise ToolError("op=update requires config")
        updated = _replace(data, structure, id, config)
        if not updated:
            raise ToolError(f"{kind} '{id}' not found")
        await _save(hass, path, data, structure)
        await _reload(hass, reload_domain)
        return {"id": id, "updated": True}

    if op == "delete":
        if not id:
            raise ToolError("op=delete requires id")
        removed = _remove(data, structure, id)
        if not removed:
            raise ToolError(f"{kind} '{id}' not found")
        await _save(hass, path, data, structure)
        await _reload(hass, reload_domain)
        return {"id": id, "deleted": True}

    if op == "reload":
        await _reload(hass, reload_domain)
        return {"reloaded": reload_domain}

    raise ToolError(f"unsupported op '{op}'")


def _derive_entity_id(domain: str, structure: str, new_id: str, config: dict[str, Any]) -> str:
    """Approximate HA's slugification of an entry into an entity_id."""
    if structure == "dict":
        slug = slugify(new_id)
    else:
        slug = slugify(config.get("alias") or new_id)
    return f"{domain}.{slug}"


async def _load(hass: HomeAssistant, path: str, structure: str) -> Any:
    import os

    from homeassistant.util.yaml import load_yaml_dict, parse_yaml

    def _read():
        if not os.path.exists(path):
            return [] if structure == "list" else {}
        with open(path, encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return [] if structure == "list" else {}
        return parse_yaml(content)

    parsed = await hass.async_add_executor_job(_read)
    if structure == "list" and not isinstance(parsed, list):
        raise ToolError(f"{path} must be a YAML list, got {type(parsed).__name__}")
    if structure == "dict" and not isinstance(parsed, dict):
        raise ToolError(f"{path} must be a YAML mapping, got {type(parsed).__name__}")
    # Use load_yaml_dict's typing if available, otherwise rely on parse_yaml result.
    _ = load_yaml_dict
    return parsed


async def _save(hass: HomeAssistant, path: str, data: Any, structure: str) -> None:
    from homeassistant.util.yaml import save_yaml

    def _write():
        save_yaml(path, data)

    await hass.async_add_executor_job(_write)


async def _reload(hass: HomeAssistant, domain: str) -> None:
    try:
        await hass.services.async_call(domain, "reload", {}, blocking=True)
    except Exception as e:
        raise ToolError(f"{domain}.reload failed: {e}") from e


def _to_list(data: Any, structure: str) -> list[dict[str, Any]]:
    if structure == "list":
        return list(data)
    return [{"id": k, **v} for k, v in data.items()]


def _find(data: Any, structure: str, id: str) -> dict[str, Any] | None:
    if structure == "list":
        for entry in data:
            if entry.get("id") == id or entry.get("alias") == id:
                return entry
        return None
    return {"id": id, **data[id]} if id in data else None


def _replace(data: Any, structure: str, id: str, new: dict[str, Any]) -> bool:
    if structure == "list":
        for i, entry in enumerate(data):
            if entry.get("id") == id:
                data[i] = {"id": id, **{k: v for k, v in new.items() if k != "id"}}
                return True
        return False
    if id in data:
        data[id] = new
        return True
    return False


def _remove(data: Any, structure: str, id: str) -> bool:
    if structure == "list":
        for i, entry in enumerate(data):
            if entry.get("id") == id:
                del data[i]
                return True
        return False
    if id in data:
        del data[id]
        return True
    return False
