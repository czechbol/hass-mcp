"""Config flow for hass_mcp (single-instance)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

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
    TITLE,
)


class HaMcpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(
                title=TITLE,
                data={},
                options={
                    CONF_ALLOW_WRITE: user_input.get(CONF_ALLOW_WRITE, DEFAULT_ALLOW_WRITE),
                    CONF_ALLOW_DESTRUCTIVE: user_input.get(
                        CONF_ALLOW_DESTRUCTIVE, DEFAULT_ALLOW_DESTRUCTIVE
                    ),
                    CONF_ALLOW_FIRE_EVENT: user_input.get(
                        CONF_ALLOW_FIRE_EVENT, DEFAULT_ALLOW_FIRE_EVENT
                    ),
                    CONF_RATE_LIMIT_PER_MINUTE: user_input.get(
                        CONF_RATE_LIMIT_PER_MINUTE, DEFAULT_RATE_LIMIT_PER_MINUTE
                    ),
                },
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ALLOW_WRITE, default=DEFAULT_ALLOW_WRITE): bool,
                    vol.Required(CONF_ALLOW_DESTRUCTIVE, default=DEFAULT_ALLOW_DESTRUCTIVE): bool,
                    vol.Required(CONF_ALLOW_FIRE_EVENT, default=DEFAULT_ALLOW_FIRE_EVENT): bool,
                    vol.Required(
                        CONF_RATE_LIMIT_PER_MINUTE,
                        default=DEFAULT_RATE_LIMIT_PER_MINUTE,
                    ): vol.All(int, vol.Range(min=0)),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return HaMcpOptionsFlow(config_entry)


class HaMcpOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        opts = self._entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ALLOW_WRITE,
                        default=opts.get(CONF_ALLOW_WRITE, DEFAULT_ALLOW_WRITE),
                    ): bool,
                    vol.Required(
                        CONF_ALLOW_DESTRUCTIVE,
                        default=opts.get(CONF_ALLOW_DESTRUCTIVE, DEFAULT_ALLOW_DESTRUCTIVE),
                    ): bool,
                    vol.Required(
                        CONF_ALLOW_FIRE_EVENT,
                        default=opts.get(CONF_ALLOW_FIRE_EVENT, DEFAULT_ALLOW_FIRE_EVENT),
                    ): bool,
                    vol.Required(
                        CONF_RATE_LIMIT_PER_MINUTE,
                        default=opts.get(
                            CONF_RATE_LIMIT_PER_MINUTE,
                            DEFAULT_RATE_LIMIT_PER_MINUTE,
                        ),
                    ): vol.All(int, vol.Range(min=0)),
                }
            ),
        )
