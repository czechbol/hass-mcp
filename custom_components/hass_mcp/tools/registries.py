"""Unified registry tool covering entity/device/area/label/floor/category/issue."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
)
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers import (
    entity_registry as er,
)
from homeassistant.helpers import (
    floor_registry as fr,
)
from homeassistant.helpers import (
    issue_registry as ir,
)
from homeassistant.helpers import (
    label_registry as lr,
)

from ..protocol import ToolError
from ..registry import LIMIT_FIELD, OFFSET_FIELD, paginate, schema, tool

_KINDS = {"entity", "device", "area", "label", "floor", "category", "issue"}
_OPS = {"list", "get", "update", "delete", "create"}


def _entity_to_dict(e: er.RegistryEntry) -> dict[str, Any]:
    return {
        "entity_id": e.entity_id,
        "unique_id": e.unique_id,
        "platform": e.platform,
        "config_entry_id": e.config_entry_id,
        "device_id": e.device_id,
        "area_id": e.area_id,
        "disabled_by": str(e.disabled_by) if e.disabled_by else None,
        "hidden_by": str(e.hidden_by) if e.hidden_by else None,
        "name": e.name,
        "original_name": e.original_name,
        "icon": e.icon,
        "labels": sorted(e.labels or []),
        "categories": dict(e.categories or {}),
        "options": dict(e.options or {}),
    }


def _device_to_dict(d) -> dict[str, Any]:
    return {
        "id": d.id,
        "name": d.name,
        "name_by_user": d.name_by_user,
        "manufacturer": d.manufacturer,
        "model": d.model,
        "sw_version": d.sw_version,
        "hw_version": d.hw_version,
        "area_id": d.area_id,
        "config_entries": sorted(d.config_entries or []),
        "connections": [list(c) for c in (d.connections or [])],
        "identifiers": [list(i) for i in (d.identifiers or [])],
        "labels": sorted(d.labels or []),
        "disabled_by": str(d.disabled_by) if d.disabled_by else None,
    }


def _area_to_dict(a) -> dict[str, Any]:
    return {
        "id": a.id,
        "name": a.name,
        "floor_id": a.floor_id,
        "icon": a.icon,
        "labels": sorted(a.labels or []),
        "aliases": sorted(a.aliases or []),
    }


def _label_to_dict(lab) -> dict[str, Any]:
    return {
        "label_id": lab.label_id,
        "name": lab.name,
        "color": lab.color,
        "icon": lab.icon,
        "description": lab.description,
    }


def _floor_to_dict(f) -> dict[str, Any]:
    return {
        "floor_id": f.floor_id,
        "name": f.name,
        "level": f.level,
        "icon": f.icon,
        "aliases": sorted(f.aliases or []),
    }


def _issue_to_dict(i) -> dict[str, Any]:
    return {
        "domain": i.domain,
        "issue_id": i.issue_id,
        "severity": str(i.severity) if i.severity else None,
        "is_fixable": i.is_fixable,
        "is_persistent": i.is_persistent,
        "active": i.active,
        "translation_key": i.translation_key,
        "translation_placeholders": dict(i.translation_placeholders or {}),
        "learn_more_url": i.learn_more_url,
        "breaks_in_ha_version": i.breaks_in_ha_version,
    }


@tool(
    name="ha_registry",
    description=(
        "Generic registry access. 'kind' selects which registry, 'op' the action. "
        "Mutations require allow_write (and allow_destructive for delete)."
    ),
    input_schema=schema(
        properties={
            "kind": {"type": "string", "enum": sorted(_KINDS)},
            "op": {"type": "string", "enum": sorted(_OPS)},
            "id": {
                "type": "string",
                "description": "Identifier for get/update/delete (entity_id, device id, area id, label id, floor id, issue 'domain:issue_id').",
            },
            "data": {
                "type": "object",
                "additionalProperties": True,
                "description": "Fields to set on create/update. See HA developer docs for valid keys per registry.",
            },
            "limit": LIMIT_FIELD,
            "offset": OFFSET_FIELD,
        },
        required=["kind", "op"],
    ),
    read_only=False,
)
async def ha_registry(
    hass: HomeAssistant,
    kind: str,
    op: str,
    id: str | None = None,
    data: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if kind not in _KINDS:
        raise ToolError(f"unknown kind '{kind}'; one of {sorted(_KINDS)}")
    if op not in _OPS:
        raise ToolError(f"unknown op '{op}'; one of {sorted(_OPS)}")

    handlers = {
        "entity": _entity_ops,
        "device": _device_ops,
        "area": _area_ops,
        "label": _label_ops,
        "floor": _floor_ops,
        "category": _category_ops,
        "issue": _issue_ops,
    }
    return await handlers[kind](hass, op, id, data or {}, limit, offset)


async def _entity_ops(hass, op, id, data, limit, offset):
    reg = er.async_get(hass)
    if op == "list":
        items = [_entity_to_dict(e) for e in reg.entities.values()]
        return paginate(items, limit, offset)
    if op == "get":
        if not id:
            raise ToolError("entity get requires id (entity_id)")
        e = reg.async_get(id)
        if e is None:
            raise ToolError(f"entity '{id}' not in registry")
        return _entity_to_dict(e)
    if op == "update":
        if not id:
            raise ToolError("entity update requires id (entity_id)")
        try:
            updated = reg.async_update_entity(id, **data)
        except KeyError as e:
            raise ToolError(f"entity '{id}' not found") from e
        return _entity_to_dict(updated)
    if op == "delete":
        if not id:
            raise ToolError("entity delete requires id")
        reg.async_remove(id)
        return {"entity_id": id, "deleted": True}
    if op == "create":
        raise ToolError(
            "entity create is not supported (platforms create entities; use "
            "ha_config_flow to add an integration that creates them)"
        )
    raise ToolError(f"unsupported op '{op}'")


async def _device_ops(hass, op, id, data, limit, offset):
    reg = dr.async_get(hass)
    if op == "list":
        items = [_device_to_dict(d) for d in reg.devices.values()]
        return paginate(items, limit, offset)
    if op == "get":
        if not id:
            raise ToolError("device get requires id")
        d = reg.async_get(id)
        if d is None:
            raise ToolError(f"device '{id}' not found")
        return _device_to_dict(d)
    if op == "update":
        if not id:
            raise ToolError("device update requires id")
        d = reg.async_update_device(id, **data)
        if d is None:
            raise ToolError(f"device '{id}' not found")
        return _device_to_dict(d)
    if op == "delete":
        if not id:
            raise ToolError("device delete requires id")
        reg.async_remove_device(id)
        return {"device_id": id, "deleted": True}
    if op == "create":
        raise ToolError("device create is not supported via this tool")
    raise ToolError(f"unsupported op '{op}'")


async def _area_ops(hass, op, id, data, limit, offset):
    reg = ar.async_get(hass)
    if op == "list":
        items = [_area_to_dict(a) for a in reg.async_list_areas()]
        return paginate(items, limit, offset)
    if op == "get":
        if not id:
            raise ToolError("area get requires id")
        a = reg.async_get_area(id) or reg.async_get_area_by_name(id)
        if a is None:
            raise ToolError(f"area '{id}' not found")
        return _area_to_dict(a)
    if op == "create":
        name = data.get("name")
        if not name:
            raise ToolError("area create requires data.name")
        a = reg.async_create(
            name=name,
            floor_id=data.get("floor_id"),
            icon=data.get("icon"),
            labels=set(data.get("labels", []) or []) or None,
            aliases=set(data.get("aliases", []) or []) or None,
        )
        return _area_to_dict(a)
    if op == "update":
        if not id:
            raise ToolError("area update requires id")
        a = reg.async_update(id, **data)
        return _area_to_dict(a)
    if op == "delete":
        if not id:
            raise ToolError("area delete requires id")
        reg.async_delete(id)
        return {"area_id": id, "deleted": True}
    raise ToolError(f"unsupported op '{op}'")


async def _label_ops(hass, op, id, data, limit, offset):
    reg = lr.async_get(hass)
    if op == "list":
        items = [_label_to_dict(x) for x in reg.async_list_labels()]
        return paginate(items, limit, offset)
    if op == "get":
        if not id:
            raise ToolError("label get requires id")
        lab = reg.async_get_label(id)
        if lab is None:
            raise ToolError(f"label '{id}' not found")
        return _label_to_dict(lab)
    if op == "create":
        name = data.get("name")
        if not name:
            raise ToolError("label create requires data.name")
        lab = reg.async_create(
            name=name,
            color=data.get("color"),
            icon=data.get("icon"),
            description=data.get("description"),
        )
        return _label_to_dict(lab)
    if op == "update":
        if not id:
            raise ToolError("label update requires id")
        lab = reg.async_update(id, **data)
        return _label_to_dict(lab)
    if op == "delete":
        if not id:
            raise ToolError("label delete requires id")
        reg.async_delete(id)
        return {"label_id": id, "deleted": True}
    raise ToolError(f"unsupported op '{op}'")


async def _floor_ops(hass, op, id, data, limit, offset):
    reg = fr.async_get(hass)
    if op == "list":
        items = [_floor_to_dict(x) for x in reg.async_list_floors()]
        return paginate(items, limit, offset)
    if op == "get":
        if not id:
            raise ToolError("floor get requires id")
        f = reg.async_get_floor(id)
        if f is None:
            raise ToolError(f"floor '{id}' not found")
        return _floor_to_dict(f)
    if op == "create":
        name = data.get("name")
        if not name:
            raise ToolError("floor create requires data.name")
        f = reg.async_create(
            name=name,
            level=data.get("level"),
            icon=data.get("icon"),
            aliases=set(data.get("aliases", []) or []) or None,
        )
        return _floor_to_dict(f)
    if op == "update":
        if not id:
            raise ToolError("floor update requires id")
        f = reg.async_update(id, **data)
        return _floor_to_dict(f)
    if op == "delete":
        if not id:
            raise ToolError("floor delete requires id")
        reg.async_delete(id)
        return {"floor_id": id, "deleted": True}
    raise ToolError(f"unsupported op '{op}'")


async def _category_ops(hass, op, id, data, limit, offset):
    try:
        from homeassistant.helpers import category_registry as cr
    except ImportError as e:
        raise ToolError(f"category registry unavailable: {e}") from e
    reg = cr.async_get(hass)
    scope = data.get("scope")
    if op == "list":
        if not scope:
            raise ToolError("category list requires data.scope (e.g. 'automation')")
        items = [
            {
                "category_id": c.category_id,
                "name": c.name,
                "icon": c.icon,
                "scope": scope,
            }
            for c in reg.async_list_categories(scope)
        ]
        return paginate(items, limit, offset)
    if op == "create":
        if not scope or not data.get("name"):
            raise ToolError("category create requires data.scope and data.name")
        c = reg.async_create(scope=scope, name=data["name"], icon=data.get("icon"))
        return {"category_id": c.category_id, "name": c.name, "icon": c.icon}
    if op == "update":
        if not (scope and id):
            raise ToolError("category update requires data.scope and id")
        c = reg.async_update(
            scope=scope, category_id=id, **{k: v for k, v in data.items() if k != "scope"}
        )
        return {"category_id": c.category_id, "name": c.name, "icon": c.icon}
    if op == "delete":
        if not (scope and id):
            raise ToolError("category delete requires data.scope and id")
        reg.async_delete(scope=scope, category_id=id)
        return {"category_id": id, "deleted": True}
    raise ToolError(f"unsupported op '{op}'")


async def _issue_ops(hass, op, id, data, limit, offset):
    reg = ir.async_get(hass)
    if op == "list":
        items = [_issue_to_dict(i) for i in reg.issues.values()]
        return paginate(items, limit, offset)
    if op == "get":
        if not id or ":" not in id:
            raise ToolError("issue get requires id in 'domain:issue_id' form")
        dom, iid = id.split(":", 1)
        i = reg.async_get_issue(dom, iid)
        if i is None:
            raise ToolError(f"issue '{id}' not found")
        return _issue_to_dict(i)
    if op == "delete":
        if not id or ":" not in id:
            raise ToolError("issue delete requires id in 'domain:issue_id' form")
        dom, iid = id.split(":", 1)
        reg.async_delete(dom, iid)
        return {"issue": id, "deleted": True}
    raise ToolError(f"unsupported op '{op}' for issue registry (list/get/delete only)")
