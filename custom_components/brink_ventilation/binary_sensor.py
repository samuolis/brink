"""Binary sensor entity for Brink Home Ventilation."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BrinkConfigEntry
from .const import DOMAIN, PARAM_FILTER_STATUS
from .coordinator import BrinkDataCoordinator
from .entity import BrinkHomeDeviceEntity, setup_dynamic_platform

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


def _create_binary_sensor_entities(
    coordinator: BrinkDataCoordinator, new_systems: set[int]
) -> list[BrinkFilterStatusBinarySensor]:
    """Create binary sensor entities for newly discovered systems."""
    entities: list[BrinkFilterStatusBinarySensor] = []
    for system_id in new_systems:
        device = coordinator.data[system_id]
        for component in device.get("components", []):
            params = component.get("parameters", {})
            if PARAM_FILTER_STATUS in params:
                entities.append(
                    BrinkFilterStatusBinarySensor(
                        coordinator,
                        system_id,
                        PARAM_FILTER_STATUS,
                        "filter_status",
                    )
                )
                break  # One filter sensor per device
    if entities:
        _LOGGER.debug("Adding %s binary sensor entities", len(entities))
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BrinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Brink Home binary sensor platform."""
    coordinator = entry.runtime_data.coordinator
    setup_dynamic_platform(
        coordinator, entry, async_add_entities, _create_binary_sensor_entities
    )


class BrinkFilterStatusBinarySensor(BrinkHomeDeviceEntity, BinarySensorEntity):
    """Binary sensor for Brink filter status (dirty/not dirty)."""

    _attr_translation_key = "filter_status"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{DOMAIN}_{self._system_id}_filter_status"

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
