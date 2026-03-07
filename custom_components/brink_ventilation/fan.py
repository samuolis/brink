from __future__ import annotations

import logging
import math

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.percentage import int_states_in_range, percentage_to_ranged_value, ranged_value_to_percentage

from .const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    MODE_MANUAL_VALUE,
    PARAM_OPERATING_MODE,
    PARAM_VENTILATION_LEVEL,
)
from .entity import BrinkHomeDeviceEntity

_LOGGER = logging.getLogger(__name__)

SPEED_RANGE = (1, 3)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the Brink ventilation fan platform."""
    client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities = [
        BrinkHomeVentilationFanEntity(client, coordinator, system_id, PARAM_VENTILATION_LEVEL)
        for system_id, device in (coordinator.data or {}).items()
        if device.get("parameters", {}).get(PARAM_VENTILATION_LEVEL)
    ]
    async_add_entities(entities)


class BrinkHomeVentilationFanEntity(BrinkHomeDeviceEntity, FanEntity):
    """Representation of the Brink ventilation level control."""

    async def async_set_percentage(self, percentage: int) -> None:
        target_level = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        target_level = max(SPEED_RANGE[0], min(SPEED_RANGE[1], target_level))
        await self._async_write_level(str(target_level))

    async def _async_write_level(self, level_value: str) -> None:
        ventilation = self.data
        if ventilation is None or ventilation.get("value_id") is None:
            raise HomeAssistantError("Ventilation parameter is unavailable")

        params = []
        mode = self._device.get("parameters", {}).get(PARAM_OPERATING_MODE) if self._device else None
        if mode and mode.get("value_id") is not None:
            params.append((int(mode["value_id"]), MODE_MANUAL_VALUE))
        params.append((int(ventilation["value_id"]), level_value))

        await self.client.write_parameters(self.system_id, params)
        ventilation["value"] = level_value
        if mode is not None:
            mode["value"] = MODE_MANUAL_VALUE
        self.coordinator.async_set_updated_data(dict(self.coordinator.data))
        await self.coordinator.async_request_refresh()

    @property
    def percentage(self):
        """Return the current speed percentage."""
        param = self.data
        if param is None or param.get("value") is None:
            return None
        current_value = int(param["value"])
        if current_value <= 0:
            return 0
        return ranged_value_to_percentage(SPEED_RANGE, current_value)

    @property
    def speed_count(self) -> int:
        """Return the number of supported speeds."""
        return int_states_in_range(SPEED_RANGE)

    @property
    def name(self):
        return f"{self.device_name} {self.parameter_name}"

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.system_id}_{self.parameter_key}_fan"

    @property
    def supported_features(self):
        return FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON | FanEntityFeature.SET_SPEED

    @property
    def is_on(self):
        param = self.data
        if param is None or param.get("value") is None:
            return None
        return int(param["value"]) != 0

    async def async_turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        if percentage is None:
            percentage = 33
        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_write_level("0")
