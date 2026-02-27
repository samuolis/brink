"""Select entities for Brink Home Ventilation."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BrinkConfigEntry
from .automation_controller import AutomationState
from .const import (
    BYPASS_OPERATION_MAP,
    BYPASS_OPERATION_REVERSE,
    DOMAIN,
    OPERATING_MODE_MAP,
    OPERATING_MODE_REVERSE,
    PARAM_BYPASS_OPERATION,
    PARAM_EXHAUST_AIR_FLOW,
    PARAM_OPERATING_MODE,
    PARAM_SUPPLY_AIR_FLOW,
    PARAM_VENTILATION_LEVEL,
    REFRESH_DELAY,
    VENTILATION_LEVEL_MAP,
    VENTILATION_LEVEL_REVERSE,
)
from .core.brink_home_cloud import BrinkAuthError
from .entity import BrinkHomeDeviceEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BrinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Brink Home select platform."""
    coordinator = entry.runtime_data.coordinator
    known_systems: set[int] = set()

    select_configs: list[tuple[int, str, type[BrinkHomeSelectEntity]]] = [
        (PARAM_OPERATING_MODE, "mode", BrinkHomeModeSelectEntity),
        (PARAM_BYPASS_OPERATION, "bypass", BrinkHomeBypassSelectEntity),
        (PARAM_VENTILATION_LEVEL, "ventilation_level", BrinkHomeVentilationLevelSelectEntity),
    ]

    @callback
    def _async_add_new_devices() -> None:
        """Detect new devices and add select entities for them."""
        if not coordinator.data:
            return

        new_systems = set(coordinator.data) - known_systems
        if not new_systems:
            return

        known_systems.update(new_systems)
        entities: list[BrinkHomeSelectEntity] = []

        for system_id in new_systems:
            device = coordinator.data[system_id]
            found_params: set[int] = set()
            for component in device.get("components", []):
                params = component.get("parameters", {})
                for param_id, entity_key, cls in select_configs:
                    if param_id in params and param_id not in found_params:
                        entities.append(
                            cls(coordinator, system_id, param_id, entity_key)
                        )
                        found_params.add(param_id)

        if entities:
            _LOGGER.debug("Adding %s select entities", len(entities))
            async_add_entities(entities)

    _async_add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class BrinkHomeSelectEntity(BrinkHomeDeviceEntity, SelectEntity):
    """Base class for Brink select entities with shared write-then-refresh logic."""

    # Subclasses must set these
    _value_map: dict[str, str]  # value -> label
    _reverse_map: dict[str, str]  # label -> value

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        param = self._param
        if param is None:
            return None
        value = param.get("value")
        if value is None:
            return None
        return self._value_map.get(str(value))

    @property
    def options(self) -> list[str]:
        """Return the list of available options."""
        return list(self._value_map.values())

    def _validate_for_write(self, option: str) -> tuple[str, dict[str, Any], int]:
        """Validate that a write can proceed and return (api_value, param_dict, gateway_id).

        Raises HomeAssistantError if the option is unknown, the parameter is
        unavailable, the gateway is missing, or the parameter is read-only.
        """
        value = self._reverse_map.get(option)
        if value is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_option",
                translation_placeholders={"option": option},
            )

        param = self._param
        if param is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="parameter_unavailable",
                translation_placeholders={"entity_key": self._entity_key},
            )

        gateway_id = self._gateway_id
        if gateway_id is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="gateway_unavailable",
            )

        if param.get("value_id") is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="parameter_read_only",
                translation_placeholders={"entity_key": self._entity_key},
            )

        return value, param, gateway_id

    async def _write_and_refresh(
        self, gateway_id: int, params: list[tuple[int, str]]
    ) -> None:
        """Write parameter(s) to the API and trigger a coordinated refresh."""
        try:
            await self.coordinator.client.write_parameters(
                self._system_id, gateway_id, params
            )
        except HomeAssistantError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, BrinkAuthError) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={
                    "entity_key": self._entity_key,
                    "error": str(ex),
                },
            ) from ex

        await asyncio.sleep(REFRESH_DELAY)
        await self.coordinator.async_request_refresh()
        self.coordinator.start_expedited_polling()

    async def async_select_option(self, option: str) -> None:
        """Set the selected option."""
        value, param, gateway_id = self._validate_for_write(option)
        await self._write_and_refresh(gateway_id, [(param["value_id"], value)])


class BrinkHomeModeSelectEntity(BrinkHomeSelectEntity):
    """Representation of the Brink operating mode select."""

    _attr_translation_key = "operating_mode"
    _value_map = OPERATING_MODE_MAP
    _reverse_map = OPERATING_MODE_REVERSE

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{DOMAIN}_{self._system_id}_mode"


class BrinkHomeBypassSelectEntity(BrinkHomeSelectEntity):
    """Representation of the Brink bypass valve operation select."""

    _attr_translation_key = "bypass_operation"
    _value_map = BYPASS_OPERATION_MAP
    _reverse_map = BYPASS_OPERATION_REVERSE

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{DOMAIN}_{self._system_id}_bypass_operation"


class BrinkHomeVentilationLevelSelectEntity(BrinkHomeSelectEntity):
    """Representation of the Brink ventilation level select.

    Selecting a level automatically switches the operating mode to Manual
    so that the level change takes effect immediately.

    Exposes supply and exhaust air flow rates as extra state attributes
    for combined level+flow display in dashboard cards.
    """

    _attr_translation_key = "ventilation_level"
    _value_map = VENTILATION_LEVEL_MAP
    _reverse_map = VENTILATION_LEVEL_REVERSE

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        controller = self.coordinator.automation_controller
        if controller.state != AutomationState.IDLE:
            return "adaptive"
        # Fall back to normal API-based value
        param = self._param
        if param is None:
            return None
        value = param.get("value")
        if value is None:
            return None
        return self._value_map.get(str(value))

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{DOMAIN}_{self._system_id}_ventilation_level"

    @staticmethod
    def _format_flow(param: dict[str, Any] | None) -> str | None:
        """Return an air flow value with unit, e.g. '125 m³/h'."""
        if param is None:
            return None
        value = param.get("value")
        if value is None:
            return None
        try:
            return f"{float(value):.0f} m³/h"
        except (ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return supply and exhaust air flow as extra attributes."""
        return {
            "supply_air_flow": self._format_flow(
                self._get_param_any_component(PARAM_SUPPLY_AIR_FLOW)
            ),
            "exhaust_air_flow": self._format_flow(
                self._get_param_any_component(PARAM_EXHAUST_AIR_FLOW)
            ),
        }

    async def async_select_option(self, option: str) -> None:
        """Set the ventilation level, switching to Manual mode first."""
        controller = self.coordinator.automation_controller

        if option == "adaptive":
            await controller.async_activate()
            return

        # If switching away from adaptive mode, deactivate controller
        if controller.state != AutomationState.IDLE:
            await controller.async_deactivate()

        # Original logic for levels 0-3
        value, vent_param, gateway_id = self._validate_for_write(option)

        params_to_write: list[tuple[int, str]] = []
        mode_param = self._get_param_any_component(PARAM_OPERATING_MODE)
        if mode_param is None or mode_param.get("value_id") is None:
            _LOGGER.warning(
                "Operating mode parameter unavailable; ventilation level "
                "write may not take effect if device is not in Manual mode"
            )
        else:
            params_to_write.append((mode_param["value_id"], "1"))
        params_to_write.append((vent_param["value_id"], value))

        await self._write_and_refresh(gateway_id, params_to_write)
