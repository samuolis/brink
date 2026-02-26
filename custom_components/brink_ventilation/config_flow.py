"""Config flow for Brink-home."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, MIN_SCAN_INTERVAL
from .core.brink_home_cloud import BrinkAuthError, BrinkHomeCloud

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="email")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
        ),
    }
)


async def _async_test_credentials(
    hass: HomeAssistant, username: str, password: str
) -> None:
    """Test credentials by attempting to log in.

    Raises BrinkAuthError or aiohttp exceptions on failure.
    """
    session = async_get_clientsession(hass)
    temp_old_session = async_create_clientsession(
        hass, cookie_jar=aiohttp.CookieJar(unsafe=False)
    )
    try:
        client = BrinkHomeCloud(session, temp_old_session, username, password)
        await client.login()
    finally:
        await temp_old_session.close()


class BrinkHomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Brink-home."""

    VERSION = 1

    _username: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username: str = user_input[CONF_USERNAME]
            password: str = user_input[CONF_PASSWORD]
            unique_id = username.lower()
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            try:
                await _async_test_credentials(self.hass, username, password)
            except BrinkAuthError:
                errors["base"] = "invalid_auth"
            except aiohttp.ClientResponseError as err:
                if err.status == 401:
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except (aiohttp.ClientError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=username, data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        self._username = entry_data[CONF_USERNAME]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            password: str = user_input[CONF_PASSWORD]

            try:
                await _async_test_credentials(
                    self.hass, self._username, password
                )
            except BrinkAuthError:
                errors["base"] = "invalid_auth"
            except (aiohttp.ClientError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={
                        CONF_USERNAME: self._username,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={"username": self._username},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username: str = user_input[CONF_USERNAME]
            password: str = user_input[CONF_PASSWORD]

            try:
                await _async_test_credentials(self.hass, username, password)
            except BrinkAuthError:
                errors["base"] = "invalid_auth"
            except (aiohttp.ClientError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during reconfigure")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(username.lower())
                self._abort_if_unique_id_mismatch(reason="account_mismatch")
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                )

        reconfigure_entry = self._get_reconfigure_entry()
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=reconfigure_entry.data.get(CONF_USERNAME, ""),
                    ): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.EMAIL,
                            autocomplete="email",
                        )
                    ),
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Handle an options flow for Brink-home."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            scan_interval = int(user_input.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ))
            if scan_interval < MIN_SCAN_INTERVAL:
                errors["base"] = "scan_interval_too_low"
            else:
                return self.async_create_entry(title="", data=user_input)

        default_interval = (
            user_input or self.config_entry.options
        ).get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=default_interval
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=3600,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="seconds",
                        )
                    ),
                }
            ),
            errors=errors,
        )
