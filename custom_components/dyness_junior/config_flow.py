"""Config-Flow der Dyness-Junior-Integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PORT

from .const import (
    CONF_LISTEN_IP,
    CONF_SERIAL,
    DEFAULT_LISTEN_IP,
    DEFAULT_PORT,
    DOMAIN,
)


class DynessJuniorConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            serial = user_input[CONF_SERIAL].strip().upper()
            if not (4 <= len(serial) <= 40 and serial.isalnum()):
                errors[CONF_SERIAL] = "invalid_serial"
            else:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Dyness Junior Box ({serial})",
                    data={
                        CONF_SERIAL: serial,
                        CONF_PORT: user_input.get(CONF_PORT, DEFAULT_PORT),
                        CONF_LISTEN_IP: user_input.get(CONF_LISTEN_IP, DEFAULT_LISTEN_IP),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERIAL): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Optional(CONF_LISTEN_IP, default=DEFAULT_LISTEN_IP): str,
                }
            ),
            errors=errors,
        )