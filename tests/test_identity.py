"""Effective-user propagation tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.hass_mcp import ws
from custom_components.hass_mcp.identity import current_user, effective_user, user_context


def test_user_context_none_when_unset() -> None:
    # No user in context → Context with no user_id (system attribution).
    assert user_context().user_id is None
    assert effective_user() is None


def test_user_context_uses_effective_user() -> None:
    class _User:
        id = "user-123"

    token = current_user.set(_User())
    try:
        assert user_context().user_id == "user-123"
        assert effective_user().id == "user-123"
    finally:
        current_user.reset(token)


@pytest.mark.asyncio
async def test_ws_call_fails_closed_without_user() -> None:
    from homeassistant.components.websocket_api import const as ws_const

    hass = MagicMock()
    # Register a handler so lookup succeeds; the user guard should fire first.
    hass.data = {ws_const.DOMAIN: {"test/cmd": (lambda h, c, m: None, False)}}
    with pytest.raises(ws.WsCallError, match="authenticated user"):
        await ws.ws_call(hass, "test/cmd")
