"""Integration tests for ha_validate_config against HA's real validators."""

from __future__ import annotations

import pytest

from custom_components.hass_mcp.protocol import ToolError
from custom_components.hass_mcp.tools.validate import ha_validate_config


@pytest.mark.asyncio
async def test_valid_trigger(hass) -> None:
    out = await ha_validate_config(hass, triggers=[{"platform": "event", "event_type": "x"}])
    assert out["triggers"]["valid"] is True
    assert out["triggers"]["count"] == 1


@pytest.mark.asyncio
async def test_invalid_trigger(hass) -> None:
    out = await ha_validate_config(hass, triggers=[{"platform": "nonexistent_zzz"}])
    assert out["triggers"]["valid"] is False
    assert "error" in out["triggers"]


@pytest.mark.asyncio
async def test_valid_action(hass) -> None:
    out = await ha_validate_config(hass, actions=[{"delay": "00:00:01"}])
    assert out["actions"]["valid"] is True


@pytest.mark.asyncio
async def test_empty_payload_errors(hass) -> None:
    with pytest.raises(ToolError):
        await ha_validate_config(hass)
