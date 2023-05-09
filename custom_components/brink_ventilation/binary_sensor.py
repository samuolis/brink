from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.brink_ventilation import BrinkHomeDeviceEntity

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
        entities.append(BrinkFilterNeedChangeBinarySensor(client, coordinator, deviceIndex, "filters_need_change"))

    _LOGGER.info(f"entity data: {entities}")
    async_add_entities(entities)


class BrinkFilterNeedChangeBinarySensor(BrinkHomeDeviceEntity, BinarySensorEntity):
    """Class for the phone number sensor."""

    @property
    def id(self):
        return f"{DOMAIN}_{self.name}_binary_sensor"

    @property
    def unique_id(self):
        return self.id

    @property
    def name(self):
        return f"{self.coordinator.data[self.device_index]['name']} {self.device_info['name']}"

    @property
    def icon(self):
        """Return the icon of this sensor."""
        return "mdi:air-filter"

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self.data["value"] == 1
    
    @property
    def device_class(self):
        """Return the class of this sensor."""
        return BinarySensorDeviceClass.PROBLEM
    

    