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
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_AUTO_SUMMER_BASE_LEVEL,
    CONF_AUTO_WINTER_BASE_LEVEL,
    CONF_EXTRA_VENT_DURATION,
    CONF_EXTRA_VENT_SUMMER_LEVEL,
    CONF_EXTRA_VENT_WINTER_LEVEL,
    CONF_FREEZING_THRESHOLD,
    CONF_HUMIDITY_SENSOR_1,
    CONF_HUMIDITY_SENSOR_2,
    CONF_HUMIDITY_SENSOR_3,
    CONF_HUMIDITY_SPIKE_THRESHOLD,
    CONF_INDOOR_TEMPERATURE_ENTITY_1,
    CONF_INDOOR_TEMPERATURE_ENTITY_2,
    CONF_TEMPERATURE_SOURCE_ENTITY,
    DEFAULT_AUTO_SUMMER_BASE_LEVEL,
    DEFAULT_AUTO_WINTER_BASE_LEVEL,
    DEFAULT_EXTRA_VENT_DURATION,
    DEFAULT_EXTRA_VENT_SUMMER_LEVEL,
    DEFAULT_EXTRA_VENT_WINTER_LEVEL,
    DEFAULT_FREEZING_THRESHOLD,
    DEFAULT_HUMIDITY_SPIKE_THRESHOLD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_EXTRA_VENT_DURATION,
    MAX_FREEZING_THRESHOLD,
    MAX_HUMIDITY_SPIKE_THRESHOLD,
    MAX_SCAN_INTERVAL,
    MIN_EXTRA_VENT_DURATION,
    MIN_FREEZING_THRESHOLD,
    MIN_HUMIDITY_SPIKE_THRESHOLD,
    MIN_SCAN_INTERVAL,
)
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
    client = BrinkHomeCloud(session, username, password)
    try:
        await client.login()
    finally:
        await client.close()


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
            except BrinkAuthError as ex:
                errors["base"] = (
                    "invalid_auth" if ex.is_credentials_error
                    else "cannot_connect"
                )
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
            except BrinkAuthError as ex:
                errors["base"] = (
                    "invalid_auth" if ex.is_credentials_error
                    else "cannot_connect"
                )
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
            except BrinkAuthError as ex:
                errors["base"] = (
                    "invalid_auth" if ex.is_credentials_error
                    else "cannot_connect"
                )
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

    def __init__(self) -> None:
        """Initialize the options flow."""
        self._options_data: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: General settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            scan_interval = int(user_input.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ))
            if scan_interval < MIN_SCAN_INTERVAL or scan_interval > MAX_SCAN_INTERVAL:
                errors["base"] = "scan_interval_out_of_range"
            else:
                self._options_data = dict(user_input)
                try:
                    return await self.async_step_extra_ventilation()
                except Exception:
                    _LOGGER.exception(
                        "Error transitioning to extra_ventilation step"
                    )
                    errors["base"] = "unknown"

        opts = user_input or self.config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=opts.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="seconds",
                        )
                    ),
                    vol.Required(
                        CONF_FREEZING_THRESHOLD,
                        default=opts.get(
                            CONF_FREEZING_THRESHOLD, DEFAULT_FREEZING_THRESHOLD
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_FREEZING_THRESHOLD,
                            max=MAX_FREEZING_THRESHOLD,
                            step=0.5,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="\u00b0C",
                        )
                    ),
                    vol.Optional(
                        CONF_TEMPERATURE_SOURCE_ENTITY,
                        description={
                            "suggested_value": opts.get(
                                CONF_TEMPERATURE_SOURCE_ENTITY
                            )
                        },
                    ): EntitySelector(
                        EntitySelectorConfig(
                            domain="sensor",
                            device_class="temperature",
                        )
                    ),
                    vol.Optional(
                        CONF_INDOOR_TEMPERATURE_ENTITY_1,
                        description={
                            "suggested_value": opts.get(
                                CONF_INDOOR_TEMPERATURE_ENTITY_1
                            )
                        },
                    ): EntitySelector(
                        EntitySelectorConfig(
                            domain="sensor",
                            device_class="temperature",
                        )
                    ),
                    vol.Optional(
                        CONF_INDOOR_TEMPERATURE_ENTITY_2,
                        description={
                            "suggested_value": opts.get(
                                CONF_INDOOR_TEMPERATURE_ENTITY_2
                            )
                        },
                    ): EntitySelector(
                        EntitySelectorConfig(
                            domain="sensor",
                            device_class="temperature",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_extra_ventilation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: Extra ventilation settings."""
        if not self._options_data:
            self._options_data = dict(self.config_entry.options)

        if user_input is not None:
            self._options_data.update(user_input)
            return await self.async_step_adaptive()

        opts = self.config_entry.options

        return self.async_show_form(
            step_id="extra_ventilation",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_EXTRA_VENT_DURATION,
                        default=opts.get(
                            CONF_EXTRA_VENT_DURATION, DEFAULT_EXTRA_VENT_DURATION
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_EXTRA_VENT_DURATION,
                            max=MAX_EXTRA_VENT_DURATION,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="minutes",
                        )
                    ),
                    vol.Required(
                        CONF_EXTRA_VENT_SUMMER_LEVEL,
                        default=opts.get(
                            CONF_EXTRA_VENT_SUMMER_LEVEL,
                            str(DEFAULT_EXTRA_VENT_SUMMER_LEVEL),
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=["1", "2", "3"],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        CONF_EXTRA_VENT_WINTER_LEVEL,
                        default=opts.get(
                            CONF_EXTRA_VENT_WINTER_LEVEL,
                            str(DEFAULT_EXTRA_VENT_WINTER_LEVEL),
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=["1", "2", "3"],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_adaptive(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 3: Adaptive (HA) mode settings."""
        if user_input is not None:
            self._options_data.update(user_input)
            # Preserve internal flags not exposed in the options UI
            self._options_data["adaptive_active"] = self.config_entry.options.get(
                "adaptive_active", False
            )
            return self.async_create_entry(title="", data=self._options_data)

        opts = self.config_entry.options

        return self.async_show_form(
            step_id="adaptive",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_AUTO_SUMMER_BASE_LEVEL,
                        default=opts.get(
                            CONF_AUTO_SUMMER_BASE_LEVEL,
                            str(DEFAULT_AUTO_SUMMER_BASE_LEVEL),
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=["0", "1", "2", "3"],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        CONF_AUTO_WINTER_BASE_LEVEL,
                        default=opts.get(
                            CONF_AUTO_WINTER_BASE_LEVEL,
                            str(DEFAULT_AUTO_WINTER_BASE_LEVEL),
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=["0", "1", "2", "3"],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_HUMIDITY_SENSOR_1,
                        description={
                            "suggested_value": opts.get(CONF_HUMIDITY_SENSOR_1)
                        },
                    ): EntitySelector(
                        EntitySelectorConfig(
                            domain="sensor",
                            device_class="humidity",
                        )
                    ),
                    vol.Optional(
                        CONF_HUMIDITY_SENSOR_2,
                        description={
                            "suggested_value": opts.get(CONF_HUMIDITY_SENSOR_2)
                        },
                    ): EntitySelector(
                        EntitySelectorConfig(
                            domain="sensor",
                            device_class="humidity",
                        )
                    ),
                    vol.Optional(
                        CONF_HUMIDITY_SENSOR_3,
                        description={
                            "suggested_value": opts.get(CONF_HUMIDITY_SENSOR_3)
                        },
                    ): EntitySelector(
                        EntitySelectorConfig(
                            domain="sensor",
                            device_class="humidity",
                        )
                    ),
                    vol.Required(
                        CONF_HUMIDITY_SPIKE_THRESHOLD,
                        default=opts.get(
                            CONF_HUMIDITY_SPIKE_THRESHOLD,
                            DEFAULT_HUMIDITY_SPIKE_THRESHOLD,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_HUMIDITY_SPIKE_THRESHOLD,
                            max=MAX_HUMIDITY_SPIKE_THRESHOLD,
                            step=0.5,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="%/min",
                        )
                    ),
                }
            ),
        )
