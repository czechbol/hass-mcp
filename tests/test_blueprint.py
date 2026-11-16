"""ha_blueprint path-traversal guard tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components import blueprint
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.util.yaml import parse_yaml

from custom_components.hass_mcp.protocol import ToolError
from custom_components.hass_mcp.tools.blueprint import ha_blueprint

_BAD_PATHS = ["/etc/passwd", "../../secrets.yaml", "..", "foo.txt"]

# A real blueprint with one required input (no default) used via !input.
_BP_YAML = """\
blueprint:
  name: Test
  domain: automation
  input:
    target_entity:
      name: Target
trigger:
  platform: state
  entity_id: !input target_entity
action:
  service: light.turn_on
"""


def _real_blueprint() -> blueprint.Blueprint:
    return blueprint.Blueprint(
        parse_yaml(_BP_YAML), expected_domain="automation", schema=BLUEPRINT_SCHEMA
    )


def _store_with(bp: blueprint.Blueprint) -> MagicMock:
    store = MagicMock()
    store.async_get_blueprint = AsyncMock(return_value=bp)
    store.async_add_blueprint = AsyncMock()
    return store


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


@pytest.mark.asyncio
async def test_substitute_renders_real_blueprint() -> None:
    # Exercises the real BlueprintInputs API (async_substitute moved off
    # Blueprint in HA 2026.10+). A provided input must land in the output.
    hass = MagicMock()
    hass.data = {blueprint.DOMAIN: {"automation": _store_with(_real_blueprint())}}
    result = await ha_blueprint(
        hass,
        op="substitute",
        domain="automation",
        path="test.yaml",
        inputs={"target_entity": "light.kitchen"},
    )
    assert result["path"] == "test.yaml"
    assert result["rendered"]["trigger"]["entity_id"] == "light.kitchen"


@pytest.mark.asyncio
async def test_substitute_missing_input_is_tool_error() -> None:
    # A missing required input is a user error (ToolError), not an internal 500.
    hass = MagicMock()
    hass.data = {blueprint.DOMAIN: {"automation": _store_with(_real_blueprint())}}
    with pytest.raises(ToolError):
        await ha_blueprint(hass, op="substitute", domain="automation", path="test.yaml")


@pytest.mark.asyncio
async def test_import_yaml_content_parses_input_tag() -> None:
    # parse_yaml understands !input and Blueprint builds with the required schema.
    store = _store_with(_real_blueprint())
    hass = MagicMock()
    hass.data = {blueprint.DOMAIN: {"automation": store}}
    result = await ha_blueprint(
        hass,
        op="import",
        domain="automation",
        yaml_content=_BP_YAML,
        filename="imported.yaml",
    )
    assert result["saved_as"] == "imported.yaml"
    store.async_add_blueprint.assert_awaited_once()
