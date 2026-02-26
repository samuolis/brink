"""Binary sensor entity for Brink Home Ventilation."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BrinkHomeDeviceEntity
from .const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    PARAM_FILTER_STATUS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Brink Home binary sensor platform."""
    client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities = []
    for device_index, device in enumerate(coordinator.data):
        for component in device.get("components", []):
            params = component.get("parameters", {})
            if PARAM_FILTER_STATUS in params:
                entities.append(
                    BrinkFilterStatusBinarySensor(
                        client,
                        coordinator,
                        device_index,
                        PARAM_FILTER_STATUS,
                        "filter_status",
                    )
                )
                break  # One filter sensor per device

    _LOGGER.debug("Setting up %s binary sensor entities", len(entities))
    async_add_entities(entities)


class BrinkFilterStatusBinarySensor(BrinkHomeDeviceEntity, BinarySensorEntity):
    """Binary sensor for Brink filter status (dirty/not dirty)."""

    _attr_has_entity_name = True
    _attr_translation_key = "filter_status"
    _attr_icon = "mdi:air-filter"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{DOMAIN}_{self.system_id}_filter_status"

    @property
    def is_on(self) -> bool | None:
        """Return True if the filter is dirty (problem detected)."""
        param = self._param
        if param is None:
            return None
        value = param.get("value")
        if value is None:
            return None
        return str(value) == "1"
