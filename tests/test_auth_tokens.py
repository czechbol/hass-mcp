"""Regression tests: ha_auth acts on the token owner, never a substitute admin."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.hass_mcp.identity import current_user
from custom_components.hass_mcp.protocol import ToolError
from custom_components.hass_mcp.tools.auth_tokens import ha_auth


@pytest.mark.asyncio
async def test_ha_auth_fails_closed_without_user() -> None:
    with pytest.raises(ToolError, match="authenticated user"):
        await ha_auth(MagicMock(), op="current_user")


@pytest.mark.asyncio
async def test_ha_auth_uses_effective_user_not_admin() -> None:
    class _User:
        id = "non-admin-1"
        name = "Bob"
        is_owner = False
        is_admin = False
        groups = ()

    token = current_user.set(_User())
    try:
        out = await ha_auth(MagicMock(), op="current_user")
    finally:
        current_user.reset(token)
    # It reflects the caller's own (non-admin) identity — not admins[0].
    assert out["id"] == "non-admin-1"
    assert out["is_admin"] is False
