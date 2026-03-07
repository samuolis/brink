"""Adds config flow for Brink Home."""

from __future__ import annotations

import asyncio
import logging

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .core.brink_home_cloud import BrinkAuthError, BrinkHomeCloud

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class BrinkHomeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Brink Home."""

    VERSION = 1

    def __init__(self):
        self._reauth_entry = None

    async def async_step_reauth(self, entry_data):
        """Handle re-authentication for an existing config entry."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            unique_id = username.lower()
            await self.async_set_unique_id(unique_id)

            session = async_get_clientsession(self.hass)
            brink_client = BrinkHomeCloud(session, username, password)

            try:
                await brink_client.login()
            except BrinkAuthError as err:
                errors["base"] = "invalid_auth" if err.is_credentials_error else "cannot_connect"
            except aiohttp.ClientResponseError as err:
                errors["base"] = "invalid_auth" if err.status == 401 else "cannot_connect"
            except (aiohttp.ClientError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if not self._reauth_entry:
                    return self.async_create_entry(title=username, data=user_input)
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=user_input, unique_id=unique_id
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                )
                return self.async_abort(reason="reauth_successful")
            finally:
                await brink_client.close()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for Brink Home."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): int,
                }
            ),
        )
