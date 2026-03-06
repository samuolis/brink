"""Switch entity for Brink Home Ventilation extra ventilation boost."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BrinkConfigEntry
from .automation_controller import AutomationState
from .const import DOMAIN, PARAM_VENTILATION_LEVEL
from .coordinator import BrinkDataCoordinator
from .entity import BrinkHomeDeviceEntity, setup_dynamic_platform

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


def _create_switch_entities(
    coordinator: BrinkDataCoordinator, new_systems: set[int]
) -> list[BrinkExtraVentilationSwitch]:
    """Create switch entities for newly discovered systems."""
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
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BrinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Brink Home switch platform."""
    coordinator = entry.runtime_data.coordinator
    setup_dynamic_platform(coordinator, entry, async_add_entities, _create_switch_entities)


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

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes.

        Only adds boost_trigger when activated by automation (humidity spike).
        Absence of the attribute means it was activated manually.
        """
        controller = self.coordinator.automation_controller
        if controller.state != AutomationState.BOOSTED:
            return None

        trigger = controller.boost_trigger
        if trigger is None:
            return None

        attrs: dict[str, Any] = {"boost_trigger": trigger}
        if controller.boost_trigger_entity:
            attrs["boost_trigger_sensor"] = controller.boost_trigger_entity
        if controller.boost_trigger_rate is not None:
            attrs["boost_trigger_rate"] = controller.boost_trigger_rate
        return attrs

    async def async_turn_on(self, **kwargs) -> None:
        """Start the extra ventilation boost."""
        try:
            await self.coordinator.automation_controller.async_activate_extra_ventilation()
        except HomeAssistantError:
            raise
        except Exception as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="boost_failed",
                translation_placeholders={"error": str(ex)},
            ) from ex

    async def async_turn_off(self, **kwargs) -> None:
        """Cancel the extra ventilation boost."""
        try:
            await self.coordinator.automation_controller.async_cancel_extra_ventilation()
        except HomeAssistantError:
            raise
        except Exception as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="boost_failed",
                translation_placeholders={"error": str(ex)},
            ) from ex
