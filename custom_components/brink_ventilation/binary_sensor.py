"""Binary sensor entity for Brink Home Ventilation."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BrinkConfigEntry
from .const import DOMAIN, PARAM_FILTER_STATUS
from .entity import BrinkHomeDeviceEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BrinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Brink Home binary sensor platform."""
    coordinator = entry.runtime_data.coordinator
    known_systems: set[int] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Detect new devices and add binary sensor entities for them."""
        if not coordinator.data:
            return

        new_systems = set(coordinator.data) - known_systems
        if not new_systems:
            return

        known_systems.update(new_systems)
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
            async_add_entities(entities)

    _async_add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


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
