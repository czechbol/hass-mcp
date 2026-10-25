"""ha_webhook — list registered webhooks."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..protocol import ToolError
from ..registry import LIMIT_FIELD, OFFSET_FIELD, paginate, schema, tool
from ..ws import WsCallError, ws_call

_OPS = ("list",)


@tool(
    name="ha_webhook",
    description=(
        "List currently registered webhooks (id, name, integration, url, "
        "local_only). op: list. Useful for finding webhook URLs handed to "
        "external services."
    ),
    input_schema=schema(
        properties={
            "op": {"type": "string", "enum": list(_OPS)},
            "limit": LIMIT_FIELD,
            "offset": OFFSET_FIELD,
        },
        required=["op"],
    ),
    read_only=True,
    # Webhook URLs are bearer-equivalent secrets: anyone holding one can POST to
    # the automation behind it. Gate the list behind an admin token to keep them
    # out of a restricted read-only token (matches the config-entry reads).
    admin_ops=["list"],
)
async def ha_webhook(
    hass: HomeAssistant,
    op: str,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if op not in _OPS:
        raise ToolError(f"unknown op '{op}'")
    try:
        items = await ws_call(hass, "webhook/list")
    except WsCallError as e:
        raise ToolError(str(e)) from e
    return paginate(list(items or []), limit, offset)
