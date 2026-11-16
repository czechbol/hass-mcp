"""Integration test for ha_helper against a real helper component + WS API.

ws_call fails closed without an effective user, so we set the identity
contextvar to the admin user for the duration of the test (as a real request
would). Exercises the input_boolean create → list → delete round-trip.
"""

from __future__ import annotations

import pytest
from homeassistant.setup import async_setup_component

from custom_components.hass_mcp.identity import current_user
from custom_components.hass_mcp.tools.helper_entities import ha_helper


@pytest.mark.asyncio
async def test_input_boolean_create_list_delete(hass, hass_admin_user) -> None:
    assert await async_setup_component(hass, "input_boolean", {"input_boolean": {}})

    token = current_user.set(hass_admin_user)
    try:
        created = await ha_helper(
            hass, kind="input_boolean", op="create", config={"name": "HM Test"}
        )
        assert created["created"] is True
        helper_id = created["item"]["id"]

        listed = await ha_helper(hass, kind="input_boolean", op="list")
        assert any(item["id"] == helper_id for item in listed["items"])

        deleted = await ha_helper(hass, kind="input_boolean", op="delete", id=helper_id)
        assert deleted == {"deleted": True, "id": helper_id}

        after = await ha_helper(hass, kind="input_boolean", op="list")
        assert all(item["id"] != helper_id for item in after["items"])
    finally:
        current_user.reset(token)
