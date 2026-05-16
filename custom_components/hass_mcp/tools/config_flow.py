"""Driving config flows — add a new integration via MCP."""

from __future__ import annotations

from typing import Any

from homeassistant import loader
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integrations

from ..protocol import ToolError
from ..registry import LIMIT_FIELD, OFFSET_FIELD, paginate, schema, tool

_OPS = {"list_handlers", "list_progress", "init", "configure", "abort"}


def _flow_result_to_dict(r: dict[str, Any]) -> dict[str, Any]:
    out = dict(r)
    rtype = out.get("type")
    if rtype is not None:
        out["type"] = rtype.value if hasattr(rtype, "value") else str(rtype)
    schema_obj = out.pop("data_schema", None)
    if schema_obj is not None:
        try:
            out["data_schema_repr"] = repr(schema_obj)
        except Exception:  # noqa: BLE001
            pass
    return out


@tool(
    name="ha_config_flow",
    description=(
        "Drive Home Assistant config flows — same surface as the UI 'Add "
        "Integration' button. Use op=list_handlers to discover integrations "
        "available to add (only those whose code is already on disk; this tool "
        "does NOT install new integration packages). Then op=init with a domain "
        "starts a flow, and op=configure with the returned flow_id steps "
        "through forms. OAuth or external-step flows will return an auth URL "
        "in the response — open it in a browser to complete."
    ),
    input_schema=schema(
        properties={
            "op": {"type": "string", "enum": sorted(_OPS)},
            "domain": {"type": "string", "description": "Integration domain for op=init."},
            "flow_id": {"type": "string", "description": "Flow id for op=configure / op=abort."},
            "user_input": {
                "type": "object",
                "additionalProperties": True,
                "description": "Form values for op=configure.",
            },
            "show_advanced_options": {"type": "boolean", "default": False},
            "domain_pattern": {
                "type": "string",
                "description": "Glob applied to integration domain for op=list_handlers (e.g. '*tapo*', 'mqtt*').",
            },
            "name_contains": {
                "type": "string",
                "description": "Case-insensitive substring match on integration display name for op=list_handlers.",
            },
            "limit": LIMIT_FIELD,
            "offset": OFFSET_FIELD,
        },
        required=["op"],
    ),
    read_only=False,
    idempotent=False,
    requires_write=True,
)
async def ha_config_flow(
    hass: HomeAssistant,
    op: str,
    domain: str | None = None,
    flow_id: str | None = None,
    user_input: dict[str, Any] | None = None,
    show_advanced_options: bool = False,
    domain_pattern: str | None = None,
    name_contains: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if op not in _OPS:
        raise ToolError(f"unknown op '{op}'")

    if op == "list_handlers":
        return await _list_handlers(hass, domain_pattern, name_contains, limit, offset)

    if op == "list_progress":
        flows = hass.config_entries.flow.async_progress()
        items = [_flow_result_to_dict(f) for f in flows]
        return paginate(items, limit, offset)

    if op == "init":
        if not domain:
            raise ToolError("op=init requires 'domain'")
        try:
            result = await hass.config_entries.flow.async_init(
                domain,
                context={
                    "source": "user",
                    "show_advanced_options": show_advanced_options,
                },
                data=user_input,
            )
        except Exception as e:
            raise ToolError(f"flow init failed for domain '{domain}': {e}") from e
        return _flow_result_to_dict(result)

    if op == "configure":
        if not flow_id:
            raise ToolError("op=configure requires 'flow_id'")
        try:
            result = await hass.config_entries.flow.async_configure(flow_id, user_input or {})
        except Exception as e:
            raise ToolError(f"flow configure failed for '{flow_id}': {e}") from e
        return _flow_result_to_dict(result)

    if op == "abort":
        if not flow_id:
            raise ToolError("op=abort requires 'flow_id'")
        try:
            hass.config_entries.flow.async_abort(flow_id)
        except Exception as e:
            raise ToolError(f"flow abort failed for '{flow_id}': {e}") from e
        return {"flow_id": flow_id, "aborted": True}

    raise ToolError(f"unsupported op '{op}'")


async def _list_handlers(
    hass: HomeAssistant,
    domain_pattern: str | None,
    name_contains: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    import fnmatch

    try:
        flows = await loader.async_get_config_flows(hass)
    except Exception as e:
        raise ToolError(f"failed to enumerate config flows: {e}") from e

    domains = sorted(flows)
    if domain_pattern:
        domains = [d for d in domains if fnmatch.fnmatchcase(d, domain_pattern)]

    # name_contains needs integration manifests — fetch all matching candidates.
    if name_contains:
        needle = name_contains.lower()
        fetched_all = await async_get_integrations(hass, domains) if domains else {}
        domains = [
            d
            for d in domains
            if not isinstance(fetched_all.get(d), BaseException)
            and fetched_all.get(d) is not None
            and needle in (fetched_all[d].name or "").lower()
        ]

    chunk = domains[offset : offset + limit]
    fetched = await async_get_integrations(hass, chunk) if chunk else {}
    items: list[dict[str, Any]] = []
    for dom in chunk:
        info = fetched.get(dom)
        if isinstance(info, BaseException) or info is None:
            items.append({"domain": dom, "error": str(info) if info else "not found"})
            continue
        items.append(
            {
                "domain": dom,
                "name": info.name,
                "iot_class": getattr(info, "iot_class", None),
                "integration_type": getattr(info, "integration_type", None),
                "documentation": getattr(info, "documentation", None),
                "version": getattr(info, "version", None),
                "is_built_in": getattr(info, "is_built_in", True),
            }
        )
    return {
        "items": items,
        "total": len(domains),
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(chunk) < len(domains),
        "next_offset": offset + len(chunk) if offset + len(chunk) < len(domains) else None,
    }
