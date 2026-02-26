"""Button entity for Brink Home Ventilation."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BrinkConfigEntry
from .const import DOMAIN, PARAM_VENTILATION_LEVEL
from .entity import BrinkHomeDeviceEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BrinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Brink Home button platform."""
    coordinator = entry.runtime_data.coordinator
    known_systems: set[int] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Detect new devices and add button entities for them."""
        if not coordinator.data:
            return

        new_systems = set(coordinator.data) - known_systems
        if not new_systems:
            return

        known_systems.update(new_systems)
        entities: list[BrinkExtraVentilationButton] = []

        for system_id in new_systems:
            device = coordinator.data[system_id]
            for component in device.get("components", []):
                params = component.get("parameters", {})
                if PARAM_VENTILATION_LEVEL in params:
                    entities.append(
                        BrinkExtraVentilationButton(
                            coordinator,
                            system_id,
                            PARAM_VENTILATION_LEVEL,
                            "extra_ventilation",
                        )
                    )
                    break  # One button per device

        if entities:
            _LOGGER.debug("Adding %s button entities", len(entities))
            async_add_entities(entities)

    _async_add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class BrinkExtraVentilationButton(BrinkHomeDeviceEntity, ButtonEntity):
    """Button to trigger extra ventilation boost."""

    _attr_translation_key = "extra_ventilation"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{DOMAIN}_{self._system_id}_extra_ventilation"

    async def async_press(self) -> None:
        """Handle the button press to activate extra ventilation."""
        await self.coordinator.automation_controller.async_activate_extra_ventilation()
