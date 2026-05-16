"""Service catalog + call_service."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceNotFound,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import translation
from homeassistant.helpers.service import async_get_all_descriptions

from ..protocol import ToolError
from ..registry import LIMIT_FIELD, OFFSET_FIELD, paginate, schema, tool


@tool(
    name="ha_list_services",
    description=(
        "List available services with rich field descriptions, selectors, examples, "
        "and target shape — same data that powers the HA UI's service picker. "
        "Pass these to ha_call_service."
    ),
    input_schema=schema(
        properties={
            "domain": {"type": "string", "description": "Filter to a single domain."},
            "service_pattern": {
                "type": "string",
                "description": "fnmatch glob applied to '<domain>.<service>' (e.g. 'light.*', '*.turn_on').",
            },
            "limit": LIMIT_FIELD,
            "offset": OFFSET_FIELD,
        }
    ),
    read_only=True,
)
async def ha_list_services(
    hass: HomeAssistant,
    domain: str | None = None,
    service_pattern: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    import fnmatch

    descriptions = await async_get_all_descriptions(hass)
    services = hass.services.async_services()
    tx = await _service_translations(hass)

    items: list[dict[str, Any]] = []
    for dom, svc_descs in descriptions.items():
        if domain and dom != domain:
            continue
        for sname, desc in svc_descs.items():
            full = f"{dom}.{sname}"
            if service_pattern and not fnmatch.fnmatchcase(full, service_pattern):
                continue
            svc = services.get(dom, {}).get(sname)
            merged = _merge_translation(desc, dom, sname, tx)
            entry: dict[str, Any] = {
                "domain": dom,
                "name": sname,
                "id": full,
                "display_name": merged["name"],
                "description": merged["description"],
                "fields": merged["fields"],
                "target": merged["target"],
                "supports_response": _response_str(svc),
                "response": merged["response"],
            }
            items.append(entry)
    items.sort(key=lambda e: e["id"])
    return paginate(items, limit, offset)


async def _preload_service_translations(hass: HomeAssistant) -> None:
    """No-op kept for API stability; merge happens in _service_translations()."""


async def _service_translations(hass: HomeAssistant) -> dict[str, str]:
    """Return mapping of service translation keys to localized text.

    Keys look like ``component.<domain>.services.<service>.name`` and
    ``component.<domain>.services.<service>.description``. HA stores these
    separately from services.yaml and async_get_all_descriptions() does not
    merge them.
    """
    lang = hass.config.language or "en"
    components = set(hass.services.async_services())
    try:
        return await translation.async_get_translations(hass, lang, "services", components, False)
    except Exception:  # noqa: BLE001
        return {}


def _merge_translation(
    desc: dict[str, Any], dom: str, sname: str, tx: dict[str, str]
) -> dict[str, Any]:
    base = f"component.{dom}.services.{sname}"
    name = tx.get(f"{base}.name")
    description = tx.get(f"{base}.description")
    fields = dict(desc.get("fields") or {})
    if fields:
        # Merge field-level name/description from translations into each field entry.
        for fname, fmeta in list(fields.items()):
            if not isinstance(fmeta, dict):
                continue
            fbase = f"{base}.fields.{fname}"
            fn = tx.get(f"{fbase}.name")
            fd = tx.get(f"{fbase}.description")
            new = dict(fmeta)
            if fn:
                new.setdefault("name", fn)
            if fd:
                new.setdefault("description", fd)
            fields[fname] = new
    return {
        "name": name or desc.get("name") or "",
        "description": description or desc.get("description") or "",
        "fields": fields,
        "target": desc.get("target"),
        "response": desc.get("response"),
    }


@tool(
    name="ha_describe_service",
    description=(
        "Describe a single service by id (e.g. 'light.turn_on'). Returns "
        "description, field schemas, selectors, examples, target shape, and "
        "supports_response."
    ),
    input_schema=schema(
        properties={
            "id": {"type": "string", "description": "Service id 'domain.service'."},
        },
        required=["id"],
    ),
    read_only=True,
)
async def ha_describe_service(hass: HomeAssistant, id: str) -> dict[str, Any]:
    if "." not in id:
        raise ToolError("service id must be 'domain.service' format")
    dom, sname = id.split(".", 1)
    services = hass.services.async_services()
    svc = services.get(dom, {}).get(sname)
    if svc is None:
        raise ToolError(f"service '{id}' not found; use ha_list_services")

    descriptions = await async_get_all_descriptions(hass)
    desc = descriptions.get(dom, {}).get(sname, {})
    tx = await _service_translations(hass)
    merged = _merge_translation(desc, dom, sname, tx)

    return {
        "domain": dom,
        "name": sname,
        "id": id,
        "display_name": merged["name"],
        "description": merged["description"],
        "fields": merged["fields"],
        "target": merged["target"],
        "supports_response": _response_str(svc),
        "response": merged["response"],
    }


def _response_str(svc) -> str:
    resp = getattr(svc, "supports_response", None) if svc else None
    if resp is None:
        return "none"
    if isinstance(resp, SupportsResponse):
        return resp.value
    return str(resp)


@tool(
    name="ha_call_service",
    description=(
        "Call any Home Assistant service. Primary write surface for controlling "
        "devices and triggering automations/scripts/scenes. Find services with "
        "ha_list_services. `return_response` is auto-detected from the service's "
        "supports_response flag — leave at default unless overriding."
    ),
    input_schema=schema(
        properties={
            "domain": {"type": "string"},
            "service": {"type": "string"},
            "service_data": {
                "type": "object",
                "additionalProperties": True,
                "description": "Service-specific data fields (e.g. brightness, color_temp).",
            },
            "target": {
                "type": "object",
                "additionalProperties": True,
                "description": "Optional target with entity_id / device_id / area_id / label_id / floor_id.",
            },
            "return_response": {
                "type": "boolean",
                "description": (
                    "Force-override return_response. Default behavior: auto-detect "
                    "from the service's supports_response (ONLY → true, OPTIONAL → "
                    "true, NONE → false)."
                ),
            },
            "blocking": {"type": "boolean", "default": True},
        },
        required=["domain", "service"],
    ),
    read_only=False,
    idempotent=False,
    requires_write=True,
)
async def ha_call_service(
    hass: HomeAssistant,
    domain: str,
    service: str,
    service_data: dict[str, Any] | None = None,
    target: dict[str, Any] | None = None,
    return_response: bool | None = None,
    blocking: bool = True,
) -> dict[str, Any]:
    svc = hass.services.async_services().get(domain, {}).get(service)
    if svc is None:
        raise ToolError(f"service {domain}.{service} not found; use ha_list_services to discover")

    resp_mode = getattr(svc, "supports_response", SupportsResponse.NONE)
    if return_response is None:
        return_response = resp_mode in (
            SupportsResponse.ONLY,
            SupportsResponse.OPTIONAL,
        )
    if return_response and resp_mode == SupportsResponse.NONE:
        raise ToolError(
            f"service {domain}.{service} does not support a response "
            f"(supports_response=NONE); set return_response=false"
        )

    try:
        result = await hass.services.async_call(
            domain,
            service,
            service_data=service_data or {},
            target=target,
            blocking=blocking,
            return_response=return_response,
        )
    except ServiceNotFound as e:
        raise ToolError(f"service {domain}.{service} not found; use ha_list_services") from e
    except ServiceValidationError as e:
        raise ToolError(f"service validation error: {e}") from e
    except Unauthorized as e:
        raise ToolError(f"unauthorized: {e}") from e
    except vol.Invalid as e:
        raise ToolError(f"invalid service data: {e}") from e
    except HomeAssistantError as e:
        raise ToolError(f"{domain}.{service} failed: {type(e).__name__}: {e}") from e

    return {
        "domain": domain,
        "service": service,
        "return_response": return_response,
        "response": result if return_response else None,
        "called": True,
    }
