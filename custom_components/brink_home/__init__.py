"""Support for the Brink-home API."""
from datetime import timedelta
import logging
import asyncio

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed
)

from .const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DATA_DEVICES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN
)
from .core.brink_home_cloud import BrinkHomeCloud

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SELECT]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Brink home from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    session = async_get_clientsession(hass)
    brink_client = BrinkHomeCloud(session, username, password)

    try:
        await brink_client.login()
    except (asyncio.TimeoutError, aiohttp.ClientError) as ex:
        if ex.status == 401:
            raise ConfigEntryAuthFailed from ex

        raise ConfigEntryNotReady from ex
    except Exception as ex:
        _LOGGER.error("Failed to setup Brink: %s", ex)
        return False

    async def async_update_data():
        try:
            return await async_get_devices(hass, entry, brink_client)
        except:
            pass

        try:
            await brink_client.login()
            return await async_get_devices(hass, entry, brink_client)
        except Exception as ex:
            _LOGGER.exception("Unknown error occurred during Brink home update request: %s", ex)
            raise UpdateFailed(ex) from ex

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: brink_client,
        DATA_COORDINATOR: coordinator,
        DATA_DEVICES: [],
    }

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    # Setup components
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_get_devices(hass: HomeAssistant, entry: ConfigEntry, brink_client: BrinkHomeCloud):
    """Fetch data from Brink Home API."""

    await brink_client.login()

    systems = await brink_client.get_systems()

    # Retrieve additional description
    for system in systems:
        description = await brink_client.get_description_values(system["system_id"], system["gateway_id"])
        system["ventilation"] = description["ventilation"]
        system["mode"] = description["mode"]

    hass.data[DOMAIN][entry.entry_id][DATA_DEVICES] = systems

    return systems


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class BrinkHomeDeviceEntity(CoordinatorEntity):
    """Defines a base Brink home device entity."""

    def __init__(self, client, coordinator, device_index, entity_name):
        """Initialize the Brink home entity."""
        super().__init__(coordinator)
        self.client = client
        self.device_index = device_index
        self.entity_name = entity_name
        self.system_id = self.coordinator.data[self.device_index]["system_id"]
        self.gateway_id = self.coordinator.data[self.device_index]["gateway_id"]

    @property
    def data(self):
        """Shortcut to access data for the entity."""
        return self.coordinator.data[self.device_index][self.entity_name]

    @property
    def device_info(self):
        """Return device info for the Brink home entity."""
        return {
            "name": self.data["name"],
        }