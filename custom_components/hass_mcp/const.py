"""Constants for the hass_mcp integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "hass_mcp"
TITLE: Final = "Fully Featured Home Assistant MCP Server"

VIEW_URL: Final = "/api/hass_mcp"

CONF_ALLOW_WRITE: Final = "allow_write"
CONF_ALLOW_DESTRUCTIVE: Final = "allow_destructive"
CONF_ALLOW_FIRE_EVENT: Final = "allow_fire_event"
CONF_RATE_LIMIT_PER_MINUTE: Final = "rate_limit_per_minute"

DEFAULT_ALLOW_WRITE: Final = True
DEFAULT_ALLOW_DESTRUCTIVE: Final = False
DEFAULT_ALLOW_FIRE_EVENT: Final = False
DEFAULT_RATE_LIMIT_PER_MINUTE: Final = 600

PROTOCOL_VERSION: Final = "2025-06-18"
SERVER_NAME: Final = "hass_mcp"
SERVER_VERSION: Final = "1.0.0"
