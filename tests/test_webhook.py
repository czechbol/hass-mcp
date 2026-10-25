"""ha_webhook admin-gating tests.

Webhook URLs are bearer-equivalent secrets, so the list op is admin-gated via
``admin_ops`` (enforced centrally in protocol.py ``_tools_call``). These tests
cover the classification and the non-admin refusal through dispatch.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hass_mcp import protocol as protocol_mod
from custom_components.hass_mcp import tools  # noqa: F401  (register all tools)
from custom_components.hass_mcp.protocol import dispatch
from custom_components.hass_mcp.registry import TOOLS
from custom_components.hass_mcp.tools import webhook


@pytest.fixture
def hass() -> MagicMock:
    mock = MagicMock()
    mock.data = {protocol_mod.DOMAIN: {"options": {}}}
    return mock


class _NonAdmin:
    is_admin = False


class _Admin:
    is_admin = True


async def _call(hass: MagicMock, args: dict, user: object) -> dict:
    return await dispatch(
        hass,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "ha_webhook", "arguments": args},
        },
        user,
    )


def test_webhook_list_is_admin_gated() -> None:
    # Guards against gate drift: the list op must stay admin-gated.
    assert TOOLS["ha_webhook"].admin_ops == frozenset({"list"})


@pytest.mark.asyncio
async def test_webhook_list_blocks_non_admin(hass: MagicMock) -> None:
    resp = await _call(hass, {"op": "list"}, _NonAdmin())
    assert resp["result"]["isError"] is True
    assert "administrator" in resp["result"]["content"][0]["text"]


@pytest.mark.asyncio
async def test_webhook_list_fails_closed_without_user(hass: MagicMock) -> None:
    resp = await _call(hass, {"op": "list"}, None)
    assert resp["result"]["isError"] is True


@pytest.mark.asyncio
async def test_webhook_list_allows_admin(hass: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        webhook,
        "ws_call",
        AsyncMock(return_value=[{"webhook_id": "abc", "url": "/api/webhook/abc"}]),
    )
    resp = await _call(hass, {"op": "list"}, _Admin())
    assert resp["result"]["isError"] is False
    assert resp["result"]["structuredContent"]["items"][0]["webhook_id"] == "abc"
