"""Assist conversation + intent dispatch."""

from __future__ import annotations

from typing import Any

from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent as intent_helper

from ..protocol import ToolError
from ..registry import schema, tool


@tool(
    name="ha_conversation",
    description=(
        "Send a text utterance through the Assist conversation pipeline. "
        "Assist uses a narrow intent grammar (HassTurnOn, HassGetState, "
        "HassLightSet, etc.) — phrase commands literally ('turn on the kitchen "
        "light'), not open questions. For open queries, use ha_render_template "
        "with Jinja or ha_list_states + ha_history."
    ),
    input_schema=schema(
        properties={
            "text": {"type": "string"},
            "conversation_id": {"type": "string"},
            "language": {"type": "string"},
            "agent_id": {"type": "string"},
        },
        required=["text"],
    ),
    read_only=False,
    idempotent=False,
    requires_write=True,
)
async def ha_conversation(
    hass: HomeAssistant,
    text: str,
    conversation_id: str | None = None,
    language: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
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


@tool(
    name="ha_intent",
    description=(
        "Handle a named intent (lower-level than ha_conversation). E.g. "
        "HassTurnOn, HassGetState, HassLightSet. Bare slot values are wrapped "
        "into {'value': v} automatically — pass slots={'domain':'light'} not "
        "slots={'domain':{'value':'light'}}."
    ),
    input_schema=schema(
        properties={
            "name": {"type": "string"},
            "slots": {"type": "object", "additionalProperties": True},
            "language": {"type": "string"},
        },
        required=["name"],
    ),
    read_only=False,
    idempotent=False,
    requires_write=True,
)
async def ha_intent(
    hass: HomeAssistant,
    name: str,
    slots: dict[str, Any] | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    wrapped: dict[str, Any] = {}
    for k, v in (slots or {}).items():
        if isinstance(v, dict) and "value" in v:
            wrapped[k] = v
        else:
            wrapped[k] = {"value": v}
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
