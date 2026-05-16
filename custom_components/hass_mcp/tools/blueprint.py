"""ha_blueprint — list/get/import/delete blueprints."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..protocol import ToolError
from ..registry import LIMIT_FIELD, OFFSET_FIELD, paginate, schema, tool

_DOMAINS = ("automation", "script", "template")
_OPS = ("list", "get", "import", "delete", "substitute")


@tool(
    name="ha_blueprint",
    description=(
        "Manage blueprints (reusable automation/script templates). domain ∈ "
        "{automation, script, template}. ops: list, get, import (from URL or "
        "yaml content), delete, substitute (preview rendered yaml with inputs)."
    ),
    input_schema=schema(
        properties={
            "op": {"type": "string", "enum": list(_OPS)},
            "domain": {"type": "string", "enum": list(_DOMAINS)},
            "path": {
                "type": "string",
                "description": "Path relative to blueprints/<domain>/ (e.g. 'sun_motion.yaml').",
            },
            "url": {"type": "string", "description": "URL for op=import."},
            "yaml_content": {
                "type": "string",
                "description": "Raw blueprint yaml for op=import (alternative to url).",
            },
            "filename": {"type": "string", "description": "Target filename for op=import."},
            "inputs": {
                "type": "object",
                "additionalProperties": True,
                "description": "Input values for op=substitute.",
            },
            "limit": LIMIT_FIELD,
            "offset": OFFSET_FIELD,
        },
        required=["op", "domain"],
    ),
    read_only=False,
)
async def ha_blueprint(
    hass: HomeAssistant,
    op: str,
    domain: str,
    path: str | None = None,
    url: str | None = None,
    yaml_content: str | None = None,
    filename: str | None = None,
    inputs: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if op not in _OPS:
        raise ToolError(f"unknown op '{op}'")
    if domain not in _DOMAINS:
        raise ToolError(f"unknown domain '{domain}'")

    try:
        from homeassistant.components import blueprint
    except ImportError as e:
        raise ToolError(f"blueprint component not loaded: {e}") from e

    bps = hass.data.get(blueprint.DOMAIN, {}).get(domain)
    if bps is None:
        raise ToolError(f"no blueprints registered for domain '{domain}'")

    if op == "list":
        try:
            all_bps = await bps.async_get_blueprints()
        except Exception as e:
            raise ToolError(f"blueprint list failed: {e}") from e
        items = [
            {
                "path": p,
                "metadata": _bp_metadata(bp),
            }
            for p, bp in all_bps.items()
            if bp is not None and not isinstance(bp, Exception)
        ]
        items.sort(key=lambda e: e["path"])
        return paginate(items, limit, offset)

    if op == "get":
        if not path:
            raise ToolError("op=get requires 'path'")
        try:
            bp = await bps.async_get_blueprint(path)
        except Exception as e:
            raise ToolError(f"blueprint get failed: {e}") from e
        return {"path": path, "metadata": _bp_metadata(bp), "data": bp.data}

    if op == "import":
        if not (url or yaml_content):
            raise ToolError("op=import requires either 'url' or 'yaml_content'")
        if url:
            try:
                from homeassistant.components.blueprint.importer import (
                    fetch_blueprint_from_url,
                )
            except ImportError as e:
                raise ToolError(f"blueprint import unavailable: {e}") from e
            try:
                imported = await fetch_blueprint_from_url(hass, url)
                bp_obj = imported.blueprint
                default_fname = imported.suggested_filename + ".yaml"
            except Exception as e:
                raise ToolError(f"fetch failed: {e}") from e
        else:
            try:
                import yaml as _yaml

                data = _yaml.safe_load(yaml_content)
                bp_obj = blueprint.Blueprint(data, expected_domain=domain)
                default_fname = "imported.yaml"
            except Exception as e:
                raise ToolError(f"yaml parse failed: {e}") from e

        target = filename or default_fname
        try:
            await bps.async_add_blueprint(bp_obj, target, allow_override=True)
        except Exception as e:
            raise ToolError(f"save failed: {e}") from e
        return {"saved_as": target, "metadata": _bp_metadata(bp_obj)}

    if op == "delete":
        if not path:
            raise ToolError("op=delete requires 'path'")
        try:
            await bps.async_remove_blueprint(path)
        except Exception as e:
            raise ToolError(f"delete failed: {e}") from e
        return {"path": path, "deleted": True}

    if op == "substitute":
        if not path:
            raise ToolError("op=substitute requires 'path'")
        try:
            bp = await bps.async_get_blueprint(path)
            rendered = bp.async_substitute({"use_blueprint": {"path": path, "input": inputs or {}}})
        except Exception as e:
            raise ToolError(f"substitute failed: {e}") from e
        return {"path": path, "rendered": rendered}

    raise ToolError(f"unsupported op '{op}'")


def _bp_metadata(bp) -> dict[str, Any]:
    meta = dict(bp.metadata or {})
    inputs = meta.get("input")
    if inputs:
        meta["input"] = {
            k: (
                {
                    "name": v.get("name") if isinstance(v, dict) else None,
                    "default": v.get("default") if isinstance(v, dict) else None,
                }
                if isinstance(v, dict)
                else v
            )
            for k, v in inputs.items()
        }
    return meta
