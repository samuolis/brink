from __future__ import annotations

import logging
import math

from homeassistant.components.fan import (
    DOMAIN,
    FanEntity,
    SUPPORT_SET_SPEED
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util.percentage import int_states_in_range, ranged_value_to_percentage, percentage_to_ranged_value

from custom_components.brink_ventilation import BrinkHomeDeviceEntity

from .const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
)


_LOGGER = logging.getLogger(__name__)

SPEED_RANGE = (1, 3)  # off is not included


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the Brink Home sensor platform."""
    client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    entities = []

    _LOGGER.info(f"entity data: {coordinator.data}")
    for deviceIndex, _ in enumerate(coordinator.data):
        entities.append(BrinkHomeVentilationFanEntity(client, coordinator, deviceIndex, "ventilation"))

    _LOGGER.info(f"entity data: {entities}")
    async_add_entities(entities)


class BrinkHomeVentilationFanEntity(BrinkHomeDeviceEntity, FanEntity):

    async def async_set_percentage(self, percentage: int) -> None:
        await self.__async_updateData(math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage)))
    
    async def __async_updateData(self, value: int) -> None:
        mode = self.coordinator.data[self.device_index]["mode"]
        await self.client.set_ventilation_value(self.system_id, self.gateway_id, mode, self.data, value)
        self.coordinator.data[self.device_index][self.entity_name]["value"] = value
        self.coordinator.data[self.device_index]["mode"]["value"] = "1"

    @property
    def percentage(self):
        """Return the current speed percentage."""
        return ranged_value_to_percentage(SPEED_RANGE, int(self.data["value"]))

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(SPEED_RANGE)

    @property
    def name(self):
        return f"{self.coordinator.data[self.device_index]['name']} {self.device_info['name']}"

    @property
    def id(self):
        return f"{DOMAIN}_{self.name}_fan"

    @property
    def unique_id(self):
        return self.id
    
    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_SET_SPEED
    
    @property
    def is_on(self):
        """If the fan currently is on or off."""
        if self.data["value"] is not None:
            return int(self.data["value"]) != 0
        return None
    
    async def async_turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""
        if percentage is None:
            percentage = 33
        self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the fan."""
        await self.__async_updateData(0)