"""Integration tests for ha_set_state / ha_delete_state against a real state machine."""

from __future__ import annotations

import pytest

from custom_components.hass_mcp.tools.states import ha_delete_state, ha_set_state


@pytest.mark.asyncio
async def test_set_state_writes_to_machine(hass) -> None:
    result = await ha_set_state(
        hass, "sensor.hm_test", "42", attributes={"unit_of_measurement": "W"}
    )
    assert result["entity_id"] == "sensor.hm_test"
    assert result["state"] == "42"

    s = hass.states.get("sensor.hm_test")
    assert s is not None
    assert s.state == "42"
    assert s.attributes["unit_of_measurement"] == "W"


@pytest.mark.asyncio
async def test_delete_state_removes_existing(hass) -> None:
    hass.states.async_set("sensor.hm_del", "1")
    result = await ha_delete_state(hass, "sensor.hm_del")
    assert result == {"entity_id": "sensor.hm_del", "removed": True}
    assert hass.states.get("sensor.hm_del") is None


@pytest.mark.asyncio
async def test_delete_state_absent_reports_false(hass) -> None:
    result = await ha_delete_state(hass, "sensor.never_existed")
    assert result == {"entity_id": "sensor.never_existed", "removed": False}
