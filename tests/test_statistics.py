"""ha_statistics handler tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.hass_mcp.tools.statistics import ha_statistics


class _Instance:
    """Recorder instance stub that runs the executor job inline."""

    async def async_add_executor_job(self, func, *args):
        return func(*args)


@pytest.mark.asyncio
async def test_metadata_passes_a_set_not_a_list() -> None:
    # HA 2026.11's recorder calls `statistic_ids.difference(...)`, which only
    # a set supports — passing a list raises AttributeError. Guard against a
    # regression back to a list.
    hass = MagicMock()
    captured: dict[str, object] = {}

    def _get_metadata(_hass, *, statistic_ids):
        captured["statistic_ids"] = statistic_ids
        return {"sensor.power": {"has_mean": True}}

    with (
        patch(
            "homeassistant.components.recorder.get_instance",
            return_value=_Instance(),
        ),
        patch(
            "homeassistant.components.recorder.statistics.get_metadata",
            side_effect=_get_metadata,
        ),
        patch(
            "custom_components.hass_mcp.tools.statistics.can_read_all_entities",
            return_value=True,
        ),
    ):
        result = await ha_statistics(hass, op="metadata", statistic_ids=["sensor.power"])

    assert result == {"metadata": {"sensor.power": {"has_mean": True}}}
    assert isinstance(captured["statistic_ids"], set)
    assert captured["statistic_ids"] == {"sensor.power"}
