"""Assist: conversation pipeline + low-level intent dispatch."""

from __future__ import annotations

from typing import Any

from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent as intent_helper

from ..protocol import ToolError
from ..registry import schema, tool


@tool(
    name="ha_assist",
    description=(
        "Invoke Home Assistant Assist. op=converse sends a text utterance through "
        "the conversation pipeline — Assist uses a narrow intent grammar "
        "(HassTurnOn, HassGetState, HassLightSet, …), so phrase commands literally "
        "('turn on the kitchen light'), not open questions; for open queries use "
        "ha_render_template or ha_list_states + ha_history. op=handle_intent calls "
        "a named intent directly (lower-level): bare slot values are wrapped into "
        "{'value': v} automatically — pass slots={'domain':'light'}."
    ),
    input_schema=schema(
        properties={
            "op": {"type": "string", "enum": ["converse", "handle_intent"]},
            "text": {"type": "string", "description": "op=converse."},
            "conversation_id": {"type": "string", "description": "op=converse."},
            "agent_id": {"type": "string", "description": "op=converse."},
            "name": {"type": "string", "description": "Intent name, op=handle_intent."},
            "slots": {
                "type": "object",
                "additionalProperties": True,
                "description": "op=handle_intent.",
            },
            "language": {"type": "string"},
        },
        required=["op"],
    ),
    read_only=False,
    idempotent=False,
    requires_write=True,
)
async def ha_assist(
    hass: HomeAssistant,
    op: str,
    text: str | None = None,
    conversation_id: str | None = None,
    agent_id: str | None = None,
    name: str | None = None,
    slots: dict[str, Any] | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    if op == "converse":
        if not text:
            raise ToolError("op=converse requires text")
        try:
            from homeassistant.components import conversation
        except ImportError as e:
            raise ToolError(f"conversation integration not loaded: {e}") from e

        result = await conversation.async_converse(
            hass,
            text=text,
            conversation_id=conversation_id,
            context=Context(),
            language=language,
            agent_id=agent_id,
        )
        return result.as_dict() if hasattr(result, "as_dict") else {"raw": repr(result)}

    if op == "handle_intent":
        if not name:
            raise ToolError("op=handle_intent requires name")
        wrapped: dict[str, Any] = {}
        for k, v in (slots or {}).items():
            wrapped[k] = v if isinstance(v, dict) and "value" in v else {"value": v}
        try:
            response = await intent_helper.async_handle(
                hass,
                "hass_mcp",
                name,
                slots=wrapped,
                text_input=None,
                language=language,
            )
        except intent_helper.IntentError as e:
            raise ToolError(f"intent error: {e}") from e
        return response.as_dict() if hasattr(response, "as_dict") else {"raw": repr(response)}

    raise ToolError(f"unknown op '{op}'; use 'converse' or 'handle_intent'")
