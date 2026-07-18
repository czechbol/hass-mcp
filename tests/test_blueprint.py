"""ha_blueprint path-traversal guard tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.components import blueprint

from custom_components.hass_mcp.protocol import ToolError
from custom_components.hass_mcp.tools.blueprint import ha_blueprint

_BAD_PATHS = ["/etc/passwd", "../../secrets.yaml", "..", "foo.txt"]


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", _BAD_PATHS)
async def test_delete_rejects_unsafe_path(bad: str) -> None:
    hass = MagicMock()
    # Provide a registered domain store so we reach the delete branch; the guard
    # must reject before async_remove_blueprint is ever called.
    store = MagicMock()
    hass.data = {blueprint.DOMAIN: {"automation": store}}
    with pytest.raises(ToolError):
        await ha_blueprint(hass, op="delete", domain="automation", path=bad)
    store.async_remove_blueprint.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("op", ["get", "substitute"])
@pytest.mark.parametrize("bad", _BAD_PATHS)
async def test_read_ops_reject_unsafe_path(op: str, bad: str) -> None:
    hass = MagicMock()
    # The guard must reject before async_get_blueprint (the filesystem read) runs.
    store = MagicMock()
    hass.data = {blueprint.DOMAIN: {"automation": store}}
    with pytest.raises(ToolError):
        await ha_blueprint(hass, op=op, domain="automation", path=bad)
    store.async_get_blueprint.assert_not_called()
