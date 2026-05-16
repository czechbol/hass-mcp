"""ha_webhook — list registered webhooks."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..protocol import ToolError
from ..registry import LIMIT_FIELD, OFFSET_FIELD, paginate, schema, tool
from ..ws import WsCallError, ws_call


@tool(
    name="ha_webhook",
    description=(
        "List currently registered webhooks (id, name, integration, url, "
        "local_only). Useful for finding webhook URLs handed to external "
        "services."
    ),
    input_schema=schema(
        properties={
            "limit": LIMIT_FIELD,
            "offset": OFFSET_FIELD,
        }
    ),
    read_only=True,
)
async def ha_webhook(
    hass: HomeAssistant,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    try:
        items = await ws_call(hass, "webhook/list")
    except WsCallError as e:
        raise ToolError(str(e)) from e
    return paginate(list(items or []), limit, offset)
