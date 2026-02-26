"""Select entities for Brink Home Ventilation."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BrinkHomeDeviceEntity, async_start_expedited_polling
from .const import (
    BYPASS_OPERATION_MAP,
    BYPASS_OPERATION_REVERSE,
    DATA_CLIENT,
    DATA_COORDINATOR,
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

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Brink Home select platform."""
    client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    select_configs = [
        (PARAM_OPERATING_MODE, "mode", BrinkHomeModeSelectEntity),
        (PARAM_BYPASS_OPERATION, "bypass", BrinkHomeBypassSelectEntity),
        (PARAM_VENTILATION_LEVEL, "ventilation_level", BrinkHomeVentilationLevelSelectEntity),
    ]

    entities = []
    for device_index, device in enumerate(coordinator.data):
        found_params = set()
        for component in device.get("components", []):
            params = component.get("parameters", {})
            for param_id, entity_key, cls in select_configs:
                if param_id in params and param_id not in found_params:
                    entities.append(
                        cls(client, coordinator, device_index, param_id, entity_key)
                    )
                    found_params.add(param_id)

    _LOGGER.debug("Setting up %s select entities", len(entities))
    async_add_entities(entities)


class BrinkHomeSelectEntity(BrinkHomeDeviceEntity, SelectEntity):
    """Base class for Brink select entities with shared write-then-refresh logic."""

    _attr_has_entity_name = True

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

    def _validate_for_write(self, option: str) -> tuple[str, dict]:
        """Validate that a write can proceed and return (api_value, param_dict).

        Raises HomeAssistantError if the option is unknown, the parameter is
        unavailable, the gateway is missing, or the parameter is read-only.
        """
        value = self._reverse_map.get(option)
        if value is None:
            raise HomeAssistantError(f"Unknown option: {option}")

        param = self._param
        if param is None:
            raise HomeAssistantError(
                f"Parameter not available for {self.entity_key}. "
                "The device may be offline."
            )

        if self._gateway_id is None:
            raise HomeAssistantError(
                "Cannot send command: gateway not available. "
                "The Brink Home portal may be experiencing issues."
            )

        if param.get("value_id") is None:
            raise HomeAssistantError(
                f"Cannot send command: parameter {self.entity_key} is read-only."
            )

        return value, param

    async def async_select_option(self, option: str) -> None:
        """Set the selected option."""
        value, param = self._validate_for_write(option)

        try:
            await self.client.write_parameter(
                self.system_id, self._gateway_id, param["value_id"], value
            )
        except Exception as ex:
            raise HomeAssistantError(
                f"Failed to set {self.entity_key}: {ex}"
            ) from ex

        await asyncio.sleep(REFRESH_DELAY)
        await self.coordinator.async_request_refresh()
        async_start_expedited_polling(self.hass, self.coordinator)


class BrinkHomeModeSelectEntity(BrinkHomeSelectEntity):
    """Representation of the Brink operating mode select."""

    _attr_translation_key = "operating_mode"
    _attr_icon = "mdi:hvac"
    _value_map = OPERATING_MODE_MAP
    _reverse_map = OPERATING_MODE_REVERSE

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{DOMAIN}_{self.system_id}_mode"


class BrinkHomeBypassSelectEntity(BrinkHomeSelectEntity):
    """Representation of the Brink bypass valve operation select."""

    _attr_translation_key = "bypass_operation"
    _attr_icon = "mdi:valve"
    _value_map = BYPASS_OPERATION_MAP
    _reverse_map = BYPASS_OPERATION_REVERSE

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{DOMAIN}_{self.system_id}_bypass_operation"


class BrinkHomeVentilationLevelSelectEntity(BrinkHomeSelectEntity):
    """Representation of the Brink ventilation level select.

    Selecting a level automatically switches the operating mode to Manual
    so that the level change takes effect immediately.

    Exposes supply and exhaust air flow rates as extra state attributes
    for combined level+flow display in dashboard cards.
    """

    _attr_translation_key = "ventilation_level"
    _attr_icon = "mdi:fan"
    _value_map = VENTILATION_LEVEL_MAP
    _reverse_map = VENTILATION_LEVEL_REVERSE

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{DOMAIN}_{self.system_id}_ventilation_level"

    @staticmethod
    def _format_flow(param: dict | None) -> str | None:
        """Return an air flow value with unit, e.g. '125 m³/h'."""
        if param is None:
            return None
        value = param.get("value")
        if value is None:
            return None
        return f"{value} m³/h"

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return supply and exhaust air flow as extra attributes."""
        return {
            "supply_air_flow": self._format_flow(
                self._parameters.get(PARAM_SUPPLY_AIR_FLOW)
            ),
            "exhaust_air_flow": self._format_flow(
                self._parameters.get(PARAM_EXHAUST_AIR_FLOW)
            ),
        }

    async def async_select_option(self, option: str) -> None:
        """Set the ventilation level, switching to Manual mode first."""
        value, vent_param = self._validate_for_write(option)

        # Switch to Manual mode (1) first so the level change takes effect
        params_to_write = []
        mode_param = self._parameters.get(PARAM_OPERATING_MODE)
        if mode_param is not None:
            mode_value_id = mode_param.get("value_id")
            if mode_value_id is not None:
                params_to_write.append((mode_value_id, "1"))
        params_to_write.append((vent_param["value_id"], value))

        try:
            await self.client.write_parameters(
                self.system_id, self._gateway_id, params_to_write
            )
        except Exception as ex:
            raise HomeAssistantError(
                f"Failed to set ventilation level: {ex}"
            ) from ex

        await asyncio.sleep(REFRESH_DELAY)
        await self.coordinator.async_request_refresh()
        async_start_expedited_polling(self.hass, self.coordinator)
