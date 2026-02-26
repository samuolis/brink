"""Support for the Brink-home API."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DATA_DEVICES,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EXPEDITED_DURATION,
    MIN_SCAN_INTERVAL,
    PARAM_SOFTWARE_LABEL,
)
from .core.brink_home_cloud import BrinkAuthError, BrinkHomeCloud

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


@callback
def async_start_expedited_polling(
    hass: HomeAssistant, coordinator: DataUpdateCoordinator
) -> None:
    """Temporarily boost polling to every 15s for 3 minutes after a write.

    Multiple calls reset the 3-minute timer so expedited mode stays active
    while the user is actively making changes.
    """
    state = getattr(coordinator, "_expedited_state", None)
    if state is None:
        state = {"unsub": None, "normal_interval": None}
        coordinator._expedited_state = state

    # Cancel existing restore timer
    if state["unsub"] is not None:
        state["unsub"]()

    # Save the normal interval only on first activation
    if state["normal_interval"] is None:
        state["normal_interval"] = coordinator.update_interval

    coordinator.update_interval = timedelta(seconds=MIN_SCAN_INTERVAL)
    _LOGGER.debug(
        "Expedited polling started (every %ss for %ss)",
        MIN_SCAN_INTERVAL,
        EXPEDITED_DURATION,
    )

    @callback
    def _restore(_now):
        """Restore the normal polling interval."""
        normal = state.get("normal_interval")
        if normal is not None:
            coordinator.update_interval = normal
            _LOGGER.debug("Expedited polling ended, restored interval to %s", normal)
        state["normal_interval"] = None
        state["unsub"] = None

    state["unsub"] = async_call_later(hass, EXPEDITED_DURATION, _restore)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Brink home from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    session = async_get_clientsession(hass)
    brink_client = BrinkHomeCloud(session, username, password)

    try:
        await brink_client.login()
    except BrinkAuthError as ex:
        raise ConfigEntryAuthFailed from ex
    except aiohttp.ClientResponseError as ex:
        if ex.status == 401:
            raise ConfigEntryAuthFailed from ex
        raise ConfigEntryNotReady from ex
    except (aiohttp.ClientError, asyncio.TimeoutError) as ex:
        raise ConfigEntryNotReady from ex

    async def async_update_data():
        """Fetch data from Brink Home API."""
        try:
            return await async_get_devices(hass, entry, brink_client)
        except BrinkAuthError as ex:
            raise ConfigEntryAuthFailed(f"Authentication failed: {ex}") from ex
        except aiohttp.ClientResponseError as ex:
            if ex.status == 401:
                try:
                    await brink_client.login()
                    return await async_get_devices(hass, entry, brink_client)
                except BrinkAuthError as retry_ex:
                    raise ConfigEntryAuthFailed(
                        f"Re-authentication failed: {retry_ex}"
                    ) from retry_ex
                except aiohttp.ClientResponseError as retry_ex:
                    if retry_ex.status == 401:
                        raise ConfigEntryAuthFailed(
                            f"Re-authentication failed (HTTP 401)"
                        ) from retry_ex
                    raise UpdateFailed(
                        f"API error during re-auth (HTTP {retry_ex.status})"
                    ) from retry_ex
                except (aiohttp.ClientError, asyncio.TimeoutError) as retry_ex:
                    raise UpdateFailed(
                        f"Connection lost during re-auth: {retry_ex}"
                    ) from retry_ex
            raise UpdateFailed(f"API error (HTTP {ex.status}): {ex.message}") from ex
        except (aiohttp.ClientError, asyncio.TimeoutError) as ex:
            raise UpdateFailed(f"Connection error: {ex}") from ex

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

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — apply new scan interval without reloading."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    new_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    new_td = timedelta(seconds=new_interval)

    # If expedited polling is active, update the interval we'll restore to
    state = getattr(coordinator, "_expedited_state", None)
    if state and state.get("normal_interval") is not None:
        state["normal_interval"] = new_td
        _LOGGER.info(
            "Scan interval updated to %ss (applies after expedited polling ends)",
            new_interval,
        )
    else:
        coordinator.update_interval = new_td
        _LOGGER.info("Scan interval updated to %s seconds", new_interval)


async def async_get_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    brink_client: BrinkHomeCloud,
) -> list[dict]:
    """Fetch all systems and their parameters from the Brink Home API."""
    systems = await brink_client.get_systems()

    devices = []
    for system in systems:
        system_id = system.get("system_id")
        if system_id is None:
            _LOGGER.warning("Skipping system with missing system_id")
            continue

        try:
            device_data = await brink_client.get_device_data(system_id)
        except (aiohttp.ClientResponseError, aiohttp.ClientError, asyncio.TimeoutError) as ex:
            _LOGGER.warning(
                "Failed to fetch data for system %s: %s", system_id, ex,
            )
            continue

        device = {
            "system_id": system_id,
            "gateway_id": system.get("gateway_id"),
            "name": system.get("name", "Brink Ventilation"),
            "serial_number": system.get("serial_number", ""),
            "gateway_state": system.get("gateway_state"),
            "components": device_data.get("components", []),
        }
        devices.append(device)

    hass.data[DOMAIN][entry.entry_id][DATA_DEVICES] = devices

    _LOGGER.debug("Fetched %s devices with parameters", len(devices))

    return devices


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)

        # Cancel expedited polling timer if active
        coordinator = data[DATA_COORDINATOR]
        state = getattr(coordinator, "_expedited_state", None)
        if state and state.get("unsub"):
            state["unsub"]()

        client = data[DATA_CLIENT]
        await client.close()

    return unload_ok


class BrinkHomeDeviceEntity(CoordinatorEntity):
    """Defines a base Brink home device entity."""

    def __init__(
        self,
        client: BrinkHomeCloud,
        coordinator: DataUpdateCoordinator,
        device_index: int,
        param_id: int,
        entity_key: str,
    ):
        """Initialize the Brink home entity."""
        super().__init__(coordinator)
        self.client = client
        self.device_index = device_index
        self.param_id = param_id
        self.entity_key = entity_key

    @property
    def _device(self) -> dict | None:
        """Return the device dict for this entity's device index."""
        data = self.coordinator.data
        if data is None or self.device_index >= len(data):
            return None
        return data[self.device_index]

    @property
    def _component(self) -> dict | None:
        """Return the component containing this entity's parameter."""
        device = self._device
        if device is None:
            return None
        for component in device.get("components", []):
            if self.param_id in component.get("parameters", {}):
                return component
        return None

    @property
    def _parameters(self) -> dict:
        """Return the parameter dict for this entity's component."""
        component = self._component
        return component.get("parameters", {}) if component else {}

    @property
    def _param(self) -> dict | None:
        """Return this entity's specific parameter dict."""
        return self._parameters.get(self.param_id)

    @property
    def system_id(self) -> int | None:
        """Return the system ID for this entity's device."""
        device = self._device
        return device.get("system_id") if device else None

    @property
    def _gateway_id(self) -> int | None:
        """Return the gateway ID for this entity's device."""
        device = self._device
        return device.get("gateway_id") if device else None

    @property
    def device_info(self):
        """Return device info for the Brink entity."""
        device = self._device
        if device is None:
            return None

        component = self._component
        model = component.get("name", DEFAULT_MODEL) if component else DEFAULT_MODEL

        sw_param = self._parameters.get(PARAM_SOFTWARE_LABEL)
        sw_version = sw_param.get("value") if sw_param else None

        return {
            "identifiers": {(DOMAIN, str(self.system_id))},
            "name": device.get("name", "Brink Ventilation"),
            "manufacturer": DEFAULT_NAME,
            "model": model,
            "serial_number": device.get("serial_number"),
            "sw_version": sw_version,
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self._device is not None
            and self._param is not None
        )
