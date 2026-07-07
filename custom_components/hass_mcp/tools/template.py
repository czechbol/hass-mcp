"""Jinja template rendering."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template as template_helper

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
    tpl = template_helper.Template(template, hass)
    try:
        # Bound execution so a runaway template can't block the event loop.
        if tpl.async_render_will_timeout(_RENDER_TIMEOUT, variables=variables):
            raise ToolError(f"template render exceeded {_RENDER_TIMEOUT:g}s; simplify the template")
        rendered = tpl.async_render(variables=variables, limited=limited)
    except TemplateError as e:
        raise ToolError(f"template error: {e}") from e
    return {"rendered": rendered}
