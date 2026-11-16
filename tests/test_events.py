"""ha_list_events / ha_fire_event unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.hass_mcp.tools.events import ha_fire_event, ha_list_events


@pytest.mark.asyncio
async def test_list_events_shapes_and_sorts() -> None:
    hass = MagicMock()
    hass.bus.async_listeners.return_value = {"state_changed": 3, "call_service": 1}
    result = await ha_list_events(hass)
    assert result["total"] == 2
    # Sorted by event_type.
    assert [i["event_type"] for i in result["items"]] == ["call_service", "state_changed"]
    assert result["items"][0] == {"event_type": "call_service", "listener_count": 1}


@pytest.mark.asyncio
async def test_list_events_paginates() -> None:
    hass = MagicMock()
    hass.bus.async_listeners.return_value = {f"e{i}": i for i in range(10)}
    result = await ha_list_events(hass, limit=3, offset=0)
    assert len(result["items"]) == 3
    assert result["total"] == 10
    assert result["has_more"] is True


@pytest.mark.asyncio
async def test_fire_event_fires_on_bus() -> None:
    hass = MagicMock()
    result = await ha_fire_event(hass, event_type="my_event", event_data={"x": 1})
    hass.bus.async_fire.assert_called_once_with("my_event", {"x": 1})
    assert result == {"event_type": "my_event", "fired": True}


@pytest.mark.asyncio
async def test_fire_event_defaults_empty_data() -> None:
    hass = MagicMock()
    await ha_fire_event(hass, event_type="my_event")
    hass.bus.async_fire.assert_called_once_with("my_event", {})
