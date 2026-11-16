"""Integration tests for ha_statistics against a real recorder.

These use Home Assistant's real ``hass`` fixture and recorder (via
``pytest-homeassistant``) instead of a ``MagicMock``, so they exercise the
actual recorder statistics API. This is the layer that catches HA-version API
drift the mock-based unit tests cannot — e.g. the HA 2026.11 change that made
``get_metadata`` require a set rather than a list.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.hass_mcp.tools.statistics import ha_statistics


@pytest.mark.asyncio
async def test_metadata_against_real_recorder(recorder_mock, hass) -> None:
    # Hits the real recorder's statistics.get_metadata. On the pre-fix code
    # (a list) this raised AttributeError on HA 2026.11 (.difference()); an
    # unknown id simply yields no metadata, but it must not crash.
    with patch(
        "custom_components.hass_mcp.tools.statistics.can_read_all_entities",
        return_value=True,
    ):
        result = await ha_statistics(hass, op="metadata", statistic_ids=["sensor.does_not_exist"])
    assert result == {"metadata": {}}
