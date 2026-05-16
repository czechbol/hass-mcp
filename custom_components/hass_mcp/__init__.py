"""hass_mcp — Home Assistant MCP server (generic tools)."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ALLOW_DESTRUCTIVE,
    CONF_ALLOW_FIRE_EVENT,
    CONF_ALLOW_WRITE,
    CONF_RATE_LIMIT_PER_MINUTE,
    DEFAULT_ALLOW_DESTRUCTIVE,
    DEFAULT_ALLOW_FIRE_EVENT,
    DEFAULT_ALLOW_WRITE,
    DEFAULT_RATE_LIMIT_PER_MINUTE,
    DOMAIN,
    VIEW_URL,
)
from .http import MCPView

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Import tool modules so they register into the TOOLS registry.
    from . import tools  # noqa: F401  (import side-effects)

    options = {
        CONF_ALLOW_WRITE: entry.options.get(CONF_ALLOW_WRITE, DEFAULT_ALLOW_WRITE),
        CONF_ALLOW_DESTRUCTIVE: entry.options.get(
            CONF_ALLOW_DESTRUCTIVE, DEFAULT_ALLOW_DESTRUCTIVE
        ),
        CONF_ALLOW_FIRE_EVENT: entry.options.get(CONF_ALLOW_FIRE_EVENT, DEFAULT_ALLOW_FIRE_EVENT),
        CONF_RATE_LIMIT_PER_MINUTE: entry.options.get(
            CONF_RATE_LIMIT_PER_MINUTE, DEFAULT_RATE_LIMIT_PER_MINUTE
        ),
    }
    hass.data[DOMAIN] = {"entry_id": entry.entry_id, "options": options}

    hass.http.register_view(MCPView(hass))
    _LOGGER.info("hass_mcp: MCP endpoint registered at %s", VIEW_URL)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # HA does not provide a public API to unregister a view; the route stays
    # but will reject calls because hass.data[DOMAIN] no longer carries options.
    hass.data.pop(DOMAIN, None)
    _LOGGER.warning("hass_mcp: entry unloaded; the /api/hass_mcp route remains until HA restart")
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    hass.data[DOMAIN]["options"] = {
        CONF_ALLOW_WRITE: entry.options.get(CONF_ALLOW_WRITE, DEFAULT_ALLOW_WRITE),
        CONF_ALLOW_DESTRUCTIVE: entry.options.get(
            CONF_ALLOW_DESTRUCTIVE, DEFAULT_ALLOW_DESTRUCTIVE
        ),
        CONF_ALLOW_FIRE_EVENT: entry.options.get(CONF_ALLOW_FIRE_EVENT, DEFAULT_ALLOW_FIRE_EVENT),
        CONF_RATE_LIMIT_PER_MINUTE: entry.options.get(
            CONF_RATE_LIMIT_PER_MINUTE, DEFAULT_RATE_LIMIT_PER_MINUTE
        ),
    }
