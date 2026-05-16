"""Camera snapshot tool."""

from __future__ import annotations

import base64
from typing import Any

from homeassistant.core import HomeAssistant

from ..protocol import ToolError
from ..registry import schema, tool


@tool(
    name="ha_camera_snapshot",
    description="Capture a single frame from a camera entity and return it as base64.",
    input_schema=schema(
        properties={
            "entity_id": {"type": "string"},
            "timeout": {"type": "number", "default": 10},
        },
        required=["entity_id"],
    ),
    read_only=True,
)
async def ha_camera_snapshot(
    hass: HomeAssistant, entity_id: str, timeout: float = 10
) -> dict[str, Any]:
    try:
        from homeassistant.components import camera
    except ImportError as e:
        raise ToolError(f"camera integration not loaded: {e}") from e

    if not entity_id.startswith("camera."):
        raise ToolError(f"entity_id must be a camera.* entity (got {entity_id})")

    try:
        image = await camera.async_get_image(hass, entity_id, timeout=timeout)
    except Exception as e:
        raise ToolError(f"failed to capture {entity_id}: {e}") from e

    return {
        "entity_id": entity_id,
        "content_type": image.content_type,
        "size_bytes": len(image.content),
        "base64": base64.b64encode(image.content).decode("ascii"),
    }
