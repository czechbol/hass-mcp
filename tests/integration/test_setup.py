"""Integration tests for the config-entry lifecycle and config flow.

Approach: these load the REAL ``hass_mcp`` custom component via the
``enable_custom_integrations`` fixture and drive it through the live
``hass.config_entries`` machinery, so ``async_setup_entry`` /
``async_unload_entry`` / the options-update listener and ``config_flow.py``
all run for real rather than being called directly.
"""

from __future__ import annotations

import pytest
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant.common import MockConfigEntry

from custom_components.hass_mcp.const import (
    CONF_ALLOW_DESTRUCTIVE,
    CONF_ALLOW_FIRE_EVENT,
    CONF_ALLOW_WRITE,
    CONF_RATE_LIMIT_PER_MINUTE,
    DOMAIN,
)


@pytest.mark.asyncio
async def test_setup_entry_propagates_options(hass, enable_custom_integrations) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_ALLOW_DESTRUCTIVE: True,
            CONF_RATE_LIMIT_PER_MINUTE: 123,
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    data = hass.data[DOMAIN]
    assert data["entry_id"] == entry.entry_id
    opts = data["options"]
    # Non-defaults from the entry propagate.
    assert opts[CONF_ALLOW_DESTRUCTIVE] is True
    assert opts[CONF_RATE_LIMIT_PER_MINUTE] == 123
    # Unset options fall back to defaults.
    assert opts[CONF_ALLOW_WRITE] is True
    assert opts[CONF_ALLOW_FIRE_EVENT] is False


@pytest.mark.asyncio
async def test_options_update_listener_refreshes(hass, enable_custom_integrations) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={CONF_ALLOW_DESTRUCTIVE: False})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN]["options"][CONF_ALLOW_DESTRUCTIVE] is False

    hass.config_entries.async_update_entry(
        entry, options={CONF_ALLOW_DESTRUCTIVE: True, CONF_RATE_LIMIT_PER_MINUTE: 42}
    )
    await hass.async_block_till_done()

    opts = hass.data[DOMAIN]["options"]
    assert opts[CONF_ALLOW_DESTRUCTIVE] is True
    assert opts[CONF_RATE_LIMIT_PER_MINUTE] == 42


@pytest.mark.asyncio
async def test_unload_entry_pops_domain(hass, enable_custom_integrations) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN in hass.data

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN not in hass.data


@pytest.mark.asyncio
async def test_user_config_flow_creates_entry(hass, enable_custom_integrations) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ALLOW_WRITE: True,
            CONF_ALLOW_DESTRUCTIVE: True,
            CONF_ALLOW_FIRE_EVENT: False,
            CONF_RATE_LIMIT_PER_MINUTE: 300,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_ALLOW_DESTRUCTIVE] is True
    assert result["options"][CONF_RATE_LIMIT_PER_MINUTE] == 300


@pytest.mark.asyncio
async def test_single_instance_only(hass, enable_custom_integrations) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.asyncio
async def test_options_flow_saves(hass, enable_custom_integrations) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={CONF_ALLOW_DESTRUCTIVE: False})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ALLOW_WRITE: True,
            CONF_ALLOW_DESTRUCTIVE: True,
            CONF_ALLOW_FIRE_EVENT: False,
            CONF_RATE_LIMIT_PER_MINUTE: 600,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_ALLOW_DESTRUCTIVE] is True
