"""Config entries (already-installed integrations) management."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from ..protocol import ToolError
from ..registry import LIMIT_FIELD, OFFSET_FIELD, paginate, schema, tool

_OPS = {"list", "get", "reload", "unload", "setup", "remove", "update_options"}


def _entry_to_dict(e: ConfigEntry) -> dict[str, Any]:
    return {
        "entry_id": e.entry_id,
        "domain": e.domain,
        "title": e.title,
        "source": e.source,
        "state": str(e.state),
        "disabled_by": str(e.disabled_by) if e.disabled_by else None,
        "unique_id": e.unique_id,
        "data": _redact(e.data),
        "options": _redact(e.options or {}),
        "pref_disable_new_entities": e.pref_disable_new_entities,
        "pref_disable_polling": e.pref_disable_polling,
        "version": e.version,
        "minor_version": getattr(e, "minor_version", None),
    }


_SECRET_SUBSTRINGS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "webhook_id",
    "auth",
    "credential",
    "pin",
)


def _is_secret_key(key: str) -> bool:
    k = key.lower()
    if k in {"username", "user", "host", "url", "port", "name"}:
        return False
    return any(s in k for s in _SECRET_SUBSTRINGS)


def _redact(d: Any) -> Any:
    if isinstance(d, Mapping):
        return {k: ("***" if _is_secret_key(str(k)) else _redact(v)) for k, v in d.items()}
    if isinstance(d, (list, tuple)):
        return [_redact(v) for v in d]
    return d


@tool(
    name="ha_config_entries",
    description=(
        "Manage existing config entries (installed integrations). For adding a new "
        "integration, use ha_config_flow."
    ),
    input_schema=schema(
        properties={
            "op": {"type": "string", "enum": sorted(_OPS)},
            "entry_id": {"type": "string"},
            "domain": {"type": "string", "description": "Filter by domain for op=list."},
            "options": {
                "type": "object",
                "additionalProperties": True,
                "description": "For op=update_options.",
            },
            "limit": LIMIT_FIELD,
            "offset": OFFSET_FIELD,
        },
        required=["op"],
    ),
    read_only=False,
)
async def ha_config_entries(
    hass: HomeAssistant,
    op: str,
    entry_id: str | None = None,
    domain: str | None = None,
    options: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if op not in _OPS:
        raise ToolError(f"unknown op '{op}'")

    if op == "list":
        entries = (
            hass.config_entries.async_entries(domain)
            if domain
            else hass.config_entries.async_entries()
        )
        return paginate([_entry_to_dict(e) for e in entries], limit, offset)

    if not entry_id and op != "list":
        raise ToolError(f"op '{op}' requires entry_id")
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        raise ToolError(f"config entry '{entry_id}' not found")

    if op == "get":
        return _entry_to_dict(entry)
    if op == "reload":
        ok = await hass.config_entries.async_reload(entry_id)
        return {"entry_id": entry_id, "reloaded": ok}
    if op == "unload":
        ok = await hass.config_entries.async_unload(entry_id)
        return {"entry_id": entry_id, "unloaded": ok}
    if op == "setup":
        await hass.config_entries.async_setup(entry_id)
        return {"entry_id": entry_id, "state": str(entry.state)}
    if op == "remove":
        result = await hass.config_entries.async_remove(entry_id)
        return {"entry_id": entry_id, "result": dict(result) if result else None}
    if op == "update_options":
        hass.config_entries.async_update_entry(entry, options=options or {})
        return _entry_to_dict(entry)
    raise ToolError(f"unsupported op '{op}'")
