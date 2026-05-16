"""ha_describe_entity — rich entity introspection."""

from __future__ import annotations

from importlib import import_module
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
from homeassistant.helpers.service import async_get_all_descriptions

from ..protocol import ToolError
from ..registry import schema, tool
from .services import _merge_translation, _service_translations


@tool(
    name="ha_describe_entity",
    description=(
        "Rich introspection of a single entity: current state, attributes, "
        "decoded supported_features bitmask, services available in its domain, "
        "and joined registry data (entry, device, area, labels). Use this "
        "before calling services to know what the entity actually supports."
    ),
    input_schema=schema(
        properties={
            "entity_id": {"type": "string"},
            "include_service_fields": {
                "type": "boolean",
                "default": False,
                "description": "If true, include the full field schema for each service in the entity's domain (verbose).",
            },
        },
        required=["entity_id"],
    ),
    read_only=True,
)
async def ha_describe_entity(
    hass: HomeAssistant,
    entity_id: str,
    include_service_fields: bool = False,
) -> dict[str, Any]:
    state = hass.states.get(entity_id)
    if state is None:
        raise ToolError(f"entity_id '{entity_id}' not found")

    domain = state.domain
    attrs = dict(state.attributes)
    out: dict[str, Any] = {
        "entity_id": entity_id,
        "domain": domain,
        "state": state.state,
        "friendly_name": attrs.get("friendly_name"),
        "attributes": attrs,
        "last_changed": state.last_changed.isoformat() if state.last_changed else None,
        "last_updated": state.last_updated.isoformat() if state.last_updated else None,
    }

    # Decode supported_features bitmask via the domain's *EntityFeature IntFlag.
    sf = attrs.get("supported_features")
    if isinstance(sf, int) and sf:
        decoded = _decode_supported_features(domain, sf)
        if decoded is not None:
            out["supported_features_decoded"] = decoded
            out["supported_features_raw"] = sf

    # Registry join.
    er_reg = er.async_get(hass)
    entry = er_reg.async_get(entity_id)
    if entry is not None:
        out["registry"] = {
            "platform": entry.platform,
            "unique_id": entry.unique_id,
            "config_entry_id": entry.config_entry_id,
            "device_id": entry.device_id,
            "area_id": entry.area_id,
            "disabled_by": str(entry.disabled_by) if entry.disabled_by else None,
            "hidden_by": str(entry.hidden_by) if entry.hidden_by else None,
            "labels": sorted(entry.labels or []),
            "categories": dict(entry.categories or {}),
            "options": dict(entry.options or {}),
        }

        if entry.device_id:
            dr_reg = dr.async_get(hass)
            device = dr_reg.async_get(entry.device_id)
            if device is not None:
                out["device"] = {
                    "id": device.id,
                    "name": device.name_by_user or device.name,
                    "manufacturer": device.manufacturer,
                    "model": device.model,
                    "sw_version": device.sw_version,
                    "area_id": device.area_id,
                }

        area_id = entry.area_id
        if not area_id and out.get("device"):
            area_id = out["device"].get("area_id")
        if area_id:
            area = ar.async_get(hass).async_get_area(area_id)
            if area is not None:
                out["area"] = {"id": area.id, "name": area.name, "floor_id": area.floor_id}

    # Services available in this domain.
    descriptions = await async_get_all_descriptions(hass)
    dom_descs = descriptions.get(domain, {})
    tx = await _service_translations(hass)
    services: list[dict[str, Any]] = []
    for sname, desc in sorted(dom_descs.items()):
        merged = _merge_translation(desc, domain, sname, tx)
        svc_entry: dict[str, Any] = {
            "id": f"{domain}.{sname}",
            "display_name": merged["name"],
            "description": merged["description"],
            "target": merged["target"],
        }
        if include_service_fields:
            svc_entry["fields"] = merged["fields"]
        services.append(svc_entry)
    out["services"] = services

    return out


_FEATURE_CLASS_NAMES = (
    "{cap}EntityFeature",  # most domains
    "{cap}Feature",
)


def _decode_supported_features(domain: str, value: int) -> list[str] | None:
    """Best-effort decode of supported_features IntFlag for a domain."""
    try:
        mod = import_module(f"homeassistant.components.{domain}")
    except ImportError:
        return None

    cap = "".join(part.capitalize() for part in domain.split("_"))
    flag_cls = None
    for tmpl in _FEATURE_CLASS_NAMES:
        flag_cls = getattr(mod, tmpl.format(cap=cap), None)
        if flag_cls is not None:
            break
    if flag_cls is None:
        # Try const submodule.
        try:
            mod_const = import_module(f"homeassistant.components.{domain}.const")
        except ImportError:
            return None
        for tmpl in _FEATURE_CLASS_NAMES:
            flag_cls = getattr(mod_const, tmpl.format(cap=cap), None)
            if flag_cls is not None:
                break
    if flag_cls is None:
        return None

    names: list[str] = []
    for member in flag_cls:
        try:
            if int(member.value) & value:
                names.append(member.name)
        except (TypeError, ValueError):
            continue
    return names or None
