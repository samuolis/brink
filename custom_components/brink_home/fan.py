from __future__ import annotations

import logging

from homeassistant.components.fan import (
    DOMAIN,
    FanEntity,
    SUPPORT_PRESET_MODE
)
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
        entities.append(BrinkHomeVentilationFanEntity(client, coordinator, deviceIndex, "ventilation"))

    _LOGGER.info(f"entity data: {entities}")
    async_add_entities(entities)


class BrinkHomeVentilationFanEntity(BrinkHomeDeviceEntity, FanEntity):

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        mode = self.coordinator.data[self.device_index]["mode"]
        await self.client.set_ventilation_value(self.system_id, self.gateway_id, mode, self.data, preset_mode)

    @property
    def preset_mode(self) -> str:
        for value in self.data["values"]:
            if value["value"] == self.data["value"]:
                return value["text"]
        return None

    @property
    def preset_modes(self) -> list[str]:
        """Return a set of selectable options."""
        values = []
        for value in self.data["values"]:
            values.append(value["text"])

        return values

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
        return SUPPORT_PRESET_MODE