from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.brink_home import BrinkHomeDeviceEntity

from .const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
)


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the Brink Home sensor platform."""
    client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    entities = []

    _LOGGER.info(f"entity data: {coordinator.data}")
    for deviceIndex, _ in enumerate(coordinator.data):
        entities.append(BrinkModeRemainingTimeSensor(client, coordinator, deviceIndex, "mode_remaining_time"))

    _LOGGER.info(f"entity data: {entities}")
    async_add_entities(entities)


class BrinkModeRemainingTimeSensor(BrinkHomeDeviceEntity, SensorEntity):
    """Class for the phone number sensor."""

    @property
    def id(self):
        return f"{DOMAIN}_{self.name}_sensor"

    @property
    def unique_id(self):
        return self.id

    @property
    def name(self):
        return f"{self.coordinator.data[self.device_index]['name']} {self.device_info['name']}"

    @property
    def icon(self):
        """Return the icon of this sensor."""
        return "mdi:fan-clock"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        current_value = self.data["value"]
        return current_value
    

    