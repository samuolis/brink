"""Support for the Brink Home API."""

from __future__ import annotations

# __init__.py
import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp
import voluptuous as vol
from aiohttp import ClientError as ClientError
from aiohttp import ClientResponseError as ClientResponseError
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.config import ConfigType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import async_get_devices
from .const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PARAM_DEVICE_TYPE,
    PARAM_SOFTWARE_LABEL,
)
from .coordinator import BrinkCoordinator
from .core.brink_home_cloud import BrinkAuthError, BrinkHomeCloud

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SELECT, Platform.BINARY_SENSOR, Platform.SENSOR, Platform.FAN, Platform.NUMBER]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


# pylint: disable=unused-argument, unnecessary-async
async def async_setup(
    hass: HomeAssistant,
    _config: ConfigType,
) -> bool:
    """Set up the Brink Ventilation integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_level",
        entity_domain=FAN_DOMAIN,
        schema={
            vol.Required("level"): vol.All(
                vol.Coerce(int),
                vol.In([0, 1, 2, 3]),
            ),
        },
        func="async_set_level",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_airflow",
        entity_domain=FAN_DOMAIN,
        schema={
            vol.Required("airflow"): vol.All(
                vol.Coerce(int),
                vol.Range(min=0, max=300),
            ),
        },
        func="async_set_airflow",
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Brink Home from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    scan_interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

    session = async_get_clientsession(hass)
    brink_client = BrinkHomeCloud(session, username, password)

    try:
        await brink_client.login()
    except BrinkAuthError as ex:
        await brink_client.close()
        raise ConfigEntryAuthFailed from ex
    except ClientResponseError as ex:
        await brink_client.close()
        if ex.status == 401:
            raise ConfigEntryAuthFailed from ex
        raise ConfigEntryNotReady from ex
    except (ClientError, asyncio.TimeoutError) as ex:
        await brink_client.close()
        raise ConfigEntryNotReady from ex
    except asyncio.CancelledError:
        await brink_client.close()
        raise

    async def async_update_data() -> dict[int, dict[str, object]]:
        try:
            return await async_get_devices(brink_client)
        except BrinkAuthError as ex:
            raise ConfigEntryAuthFailed from ex
        except ClientResponseError as ex:
            if ex.status == 401:
                raise ConfigEntryAuthFailed from ex
            raise UpdateFailed(ex) from ex
        except (ClientError, asyncio.TimeoutError) as ex:
            raise UpdateFailed(ex) from ex

    coordinator = BrinkCoordinator(
        hass=hass,
        config_entry=entry,
        brink_client=brink_client,
        scan_interval=scan_interval,
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except BaseException:
        # Release owned resources even if the task is cancelled.
        await brink_client.close()
        raise

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_CLIENT: brink_client,
        DATA_COORDINATOR: coordinator,
    }
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        await brink_client.close()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        runtime = hass.data[DOMAIN].pop(entry.entry_id)
        await runtime[DATA_CLIENT].close()
    return unload_ok
