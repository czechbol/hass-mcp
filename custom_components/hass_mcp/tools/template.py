"""Jinja template rendering."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template as template_helper

from ..identity import can_read_all_entities
from ..protocol import ToolError
from ..registry import schema, tool

# Max seconds a render may run before it's rejected (guards the event loop).
_RENDER_TIMEOUT = 3.0


@tool(
    name="ha_render_template",
    description=(
        "Render a Home Assistant Jinja template. Powerful for one-shot queries "
        "across entities (e.g. \"{{ states.sensor | selectattr('attributes.device_class','eq','temperature') | map(attribute='state') | list }}\")."
    ),
    input_schema=schema(
        properties={
            "template": {"type": "string"},
            "variables": {
                "type": "object",
                "additionalProperties": True,
                "description": "Optional Jinja variables.",
            },
            "limited": {
                "type": "boolean",
                "default": False,
                "description": "If true, restrict the template environment to safe functions only.",
            },
        },
        required=["template"],
    ),
    read_only=True,
)
async def ha_render_template(
    hass: HomeAssistant,
    template: str,
    variables: dict[str, Any] | None = None,
    limited: bool = False,
) -> dict[str, Any]:
    # A template reads state directly from hass.states — a channel we can't
    # filter per-entity — so a user whose read policy is restricted could read
    # entities they're not allowed to. Gate the whole tool on unrestricted read
    # access; admins/owner and users with full read policy are unaffected.
    if not can_read_all_entities():
        raise ToolError(
            "rendering templates requires unrestricted read access; your user's "
            "entity permissions are restricted. Use ha_get_state / ha_list_states instead"
        )

    tpl = template_helper.Template(template, hass)
    try:
        # Best-effort guard against a runaway template (HA's own safety check,
        # not a hard bound). async_render_will_timeout is a coroutine — await it.
        if await tpl.async_render_will_timeout(_RENDER_TIMEOUT, variables=variables):
            raise ToolError(f"template render exceeded {_RENDER_TIMEOUT:g}s; simplify the template")
        rendered = tpl.async_render(variables=variables, limited=limited)
    except TemplateError as e:
        raise ToolError(f"template error: {e}") from e
    return {"rendered": rendered}
