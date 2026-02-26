"""Support for the Brink-home API."""

from __future__ import annotations

from dataclasses import dataclass

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import BrinkDataCoordinator
from .core.brink_home_cloud import BrinkAuthError, BrinkHomeCloud

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
]


@dataclass
class BrinkRuntimeData:
    """Runtime data for the Brink integration."""

    client: BrinkHomeCloud
    coordinator: BrinkDataCoordinator


type BrinkConfigEntry = ConfigEntry[BrinkRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: BrinkConfigEntry) -> bool:
    """Set up Brink home from a config entry."""
    username: str = entry.data[CONF_USERNAME]
    password: str = entry.data[CONF_PASSWORD]

    session = async_get_clientsession(hass)
    old_session = async_create_clientsession(
        hass, cookie_jar=aiohttp.CookieJar(unsafe=False)
    )
    brink_client = BrinkHomeCloud(session, old_session, username, password)

    try:
        await brink_client.login()
    except BrinkAuthError as ex:
        raise ConfigEntryAuthFailed from ex
    except aiohttp.ClientResponseError as ex:
        if ex.status == 401:
            raise ConfigEntryAuthFailed from ex
        raise ConfigEntryNotReady from ex
    except (aiohttp.ClientError, TimeoutError) as ex:
        raise ConfigEntryNotReady from ex

    coordinator = BrinkDataCoordinator(hass, brink_client, entry)
    await coordinator.async_config_entry_first_refresh()

    # Restore HA automated mode if it was active before restart
    await coordinator.automation_controller.async_restore_state()

    entry.runtime_data = BrinkRuntimeData(
        client=brink_client,
        coordinator=coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: BrinkConfigEntry
) -> None:
    """Handle options update — apply new scan interval without reloading."""
    try:
        coordinator = entry.runtime_data.coordinator
    except AttributeError:
        return
    new_interval = int(entry.options.get(
        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
    ))
    await coordinator.async_update_scan_interval(new_interval)
    await coordinator.automation_controller.async_options_updated()


async def async_unload_entry(
    hass: HomeAssistant, entry: BrinkConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = entry.runtime_data.coordinator
        await coordinator.automation_controller.async_cleanup()
        coordinator.cancel_expedited_polling()
        await entry.runtime_data.client.close()

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: BrinkConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Allow removal of devices no longer returned by the API."""
    coordinator = entry.runtime_data.coordinator
    current_system_ids: set[str] = {
        str(sys_id) for sys_id in (coordinator.data or {})
    }
    device_identifiers: set[str] = {
        identifier[1]
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
    }
    # Only allow removal if the device is NOT in the current data
    return not device_identifiers.intersection(current_system_ids)
