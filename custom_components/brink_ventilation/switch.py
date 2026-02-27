"""Switch entity for Brink Home Ventilation extra ventilation boost."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BrinkConfigEntry
from .automation_controller import AutomationState
from .const import DOMAIN, PARAM_VENTILATION_LEVEL
from .entity import BrinkHomeDeviceEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BrinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Brink Home switch platform."""
    coordinator = entry.runtime_data.coordinator
    known_systems: set[int] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Detect new devices and add switch entities for them."""
        if not coordinator.data:
            return

        new_systems = set(coordinator.data) - known_systems
        if not new_systems:
            return

        known_systems.update(new_systems)
        entities: list[BrinkExtraVentilationSwitch] = []

        for system_id in new_systems:
            device = coordinator.data[system_id]
            for component in device.get("components", []):
                params = component.get("parameters", {})
                if PARAM_VENTILATION_LEVEL in params:
                    entities.append(
                        BrinkExtraVentilationSwitch(
                            coordinator,
                            system_id,
                            PARAM_VENTILATION_LEVEL,
                            "extra_ventilation",
                        )
                    )
                    break  # One switch per device

        if entities:
            _LOGGER.debug("Adding %s switch entities", len(entities))
            async_add_entities(entities)

    _async_add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class BrinkExtraVentilationSwitch(BrinkHomeDeviceEntity, SwitchEntity):
    """Switch to control extra ventilation boost.

    ON = boost is active (timer running).
    OFF = boost is not active.
    Turn ON = start the boost timer.
    Turn OFF = cancel the boost and return to previous state.
    """

    _attr_translation_key = "extra_ventilation"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{DOMAIN}_{self._system_id}_extra_ventilation"

    @property
    def is_on(self) -> bool:
        """Return True if extra ventilation boost is active."""
        return (
            self.coordinator.automation_controller.state == AutomationState.BOOSTED
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Start the extra ventilation boost."""
        await self.coordinator.automation_controller.async_activate_extra_ventilation()

    async def async_turn_off(self, **kwargs) -> None:
        """Cancel the extra ventilation boost."""
        await self.coordinator.automation_controller.async_cancel_extra_ventilation()
