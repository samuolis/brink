"""Fan controls backed by the current Brink coordinator snapshot."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.components.fan import (
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from .const import (
    CONTROL_TYPE_MAP,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    FAN_OPERATING_MODE_LABELS,
    MODE_MANUAL_VALUE,
    OPERATING_MODE_LABELS,
    PARAM_OPERATING_MODE,
    PARAM_VENTILATION_LEVEL,
    READ_WRITE_MAP,
    VALUE_STATE_MAP,
)
from .entity import BrinkHomeDeviceEntity

if TYPE_CHECKING:
    from .coordinator import BrinkCoordinator
    from .core.brink_home_cloud import BrinkHomeCloud

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_AIRFLOW = "set_airflow"
SERVICE_SET_LEVEL = "set_level"

ATTR_AIRFLOW = "airflow"
ATTR_LEVEL = "level"

SPEED_RANGE = (1, 3)
DEFAULT_ON_PERCENTAGE = 33

OPERATING_MODE_LABELS_REVERSE = {
    label: value
    for label_map in (FAN_OPERATING_MODE_LABELS, OPERATING_MODE_LABELS)
    for value, label in label_map.items()
}

FAN_PRESET_MODES: tuple[str, ...] = tuple(OPERATING_MODE_LABELS.values())


@dataclass(frozen=True, kw_only=True)
class BrinkFanEntityDescription(FanEntityDescription):
    """Describe a Brink fan entity."""

    parameter_key: str


VENTILATION_FAN_DESCRIPTION = BrinkFanEntityDescription(
    key="speed",
    translation_key="ventilation_airflow",
    parameter_key=PARAM_VENTILATION_LEVEL,
)

FAN_DESCRIPTION = BrinkFanEntityDescription(
    key="mode",
    translation_key="ventilation_level",
    parameter_key=PARAM_VENTILATION_LEVEL,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities
) -> None:
    """Set up the Brink ventilation fan platform."""
    client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities: list[FanEntity] = []

    for system_id, device in (coordinator.data or {}).items():
        if not device.parameters.get(PARAM_VENTILATION_LEVEL):
            continue

        entities.append(
            BrinkHomeVentilationFanEntity(
                client,
                coordinator,
                system_id,
            )
        )

        entities.append(
            BrinkHomeLevelFanEntity(
                client,
                coordinator,
                system_id,
            )
        )
    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_AIRFLOW,
        {
            vol.Required(ATTR_AIRFLOW): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=300)
            ),
        },
        "async_set_airflow",
    )

    platform.async_register_entity_service(
        SERVICE_SET_LEVEL,
        {
            vol.Required(ATTR_LEVEL): vol.All(
                vol.Coerce(int), vol.In([0, 1, 2, 3])
            ),
        },
        "async_set_level",
    )


class BrinkHomeBaseFanEntity(BrinkHomeDeviceEntity, FanEntity):
    """Representation of the Brink ventilation level control."""

    _attr_has_entity_name = True

    entity_description: BrinkFanEntityDescription

    def __init__(
        self,
        client: BrinkHomeCloud,
        coordinator: BrinkCoordinator,
        system_id: int,
    ) -> None:
        """Initialize the fan."""
        super().__init__(
            client,
            coordinator,
            system_id,
            self.entity_description.parameter_key,
        )

        self._level_0_max = 50
        self._level_1_max = 133
        self._level_2_max = 216

    @property
    def _max_airflow(self) -> int | None:
        """Return the current positive whole-number capacity in m³/h."""
        parameter = self._parameters.get("ventilation_mode_3_airflow")
        if not isinstance(parameter, dict):
            return None

        raw_capacity = parameter.get("max_value")
        if isinstance(raw_capacity, bool) or not isinstance(
            raw_capacity, (int, float, str)
        ):
            return None

        try:
            capacity = float(raw_capacity)
        except (TypeError, ValueError, OverflowError):
            return None

        if not math.isfinite(capacity) or capacity <= 0 or not capacity.is_integer():
            return None
        return int(capacity)

    def _require_max_airflow(self) -> int:
        """Reject airflow writes until a device and valid capacity are known."""
        if self._device is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_unavailable",
            )

        max_airflow = self._max_airflow
        if max_airflow is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="airflow_parameter_unavailable",
                translation_placeholders={"level": "3"},
            )
        return max_airflow

    @staticmethod
    def _is_airflow_writable(parameter: dict[str, object]) -> bool:
        """Require explicit vendor write access before selecting or writing airflow."""
        access = parameter.get("read_write")
        return (
            isinstance(access, int)
            and not isinstance(access, bool)
            and READ_WRITE_MAP.get(access) == "read-write"
        )

    @staticmethod
    def _validated_airflow_bounds(
        parameter: dict[str, object],
    ) -> tuple[float, float] | None:
        """Return finite writable airflow limits from the current device snapshot."""
        minimum_raw = parameter.get("min_value")
        maximum_raw = parameter.get("max_value")
        if (
            minimum_raw is None
            or maximum_raw is None
            or isinstance(minimum_raw, bool)
            or isinstance(maximum_raw, bool)
        ):
            return None
        try:
            minimum = float(minimum_raw)
            maximum = float(maximum_raw)
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(minimum) or not math.isfinite(maximum):
            return None
        return (minimum, maximum) if 0 <= minimum <= maximum else None

    def _select_airflow_level(self, airflow: int) -> int:
        """Choose a writable level able to deliver the requested exact airflow."""
        if airflow <= self._level_0_max:
            preferred_level = 0
        elif airflow <= self._level_1_max:
            preferred_level = 1
        elif airflow <= self._level_2_max:
            preferred_level = 2
        else:
            preferred_level = 3

        for level in range(preferred_level, 4):
            parameter = self._parameters.get(f"ventilation_mode_{level}_airflow")
            if not isinstance(parameter, dict) or not self._is_airflow_writable(
                parameter
            ):
                continue
            limits = self._validated_airflow_bounds(parameter)
            value_id = parameter.get("value_id")
            if limits is None or not limits[0] <= airflow <= limits[1]:
                continue
            if isinstance(value_id, bool) or not isinstance(value_id, (int, str)):
                continue
            try:
                if int(value_id) <= 0:
                    continue
            except (TypeError, ValueError, OverflowError):
                continue
            return level

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="airflow_parameter_unavailable",
            translation_placeholders={"level": str(preferred_level)},
        )

    @property
    def _ventilation_level(self) -> int | None:
        """Return a valid level or external CN1 value without inventing zero."""
        parameter = self.data
        raw_level = parameter.get("value") if parameter is not None else None
        if isinstance(raw_level, bool) or not isinstance(
            raw_level, (int, float, str)
        ):
            return None

        try:
            level = int(raw_level)
        except (TypeError, ValueError, OverflowError):
            return None

        if isinstance(raw_level, float) and raw_level != level:
            return None
        return level if level in (0, 1, 2, 3, 4) else None

    @property
    def _airflow_percentage(self) -> int | None:
        """Calculate a bounded percentage once using current cached metadata."""
        level = self._ventilation_level
        max_airflow = self._max_airflow
        if level is None or max_airflow is None:
            return None

        parameter = self._parameters.get(f"ventilation_mode_{level}_airflow")
        if not isinstance(parameter, dict):
            return None
        raw_airflow = parameter.get("value")
        if isinstance(raw_airflow, bool) or not isinstance(
            raw_airflow, (int, float, str)
        ):
            return None

        try:
            airflow = float(raw_airflow)
        except (TypeError, ValueError, OverflowError):
            return None

        if not math.isfinite(airflow) or not 0 <= airflow <= max_airflow:
            return None

        percentage = round(airflow / max_airflow * 100)
        _LOGGER.debug("percentage=%s airflow=%s", percentage, airflow)
        return percentage

    async def async_set_airflow(self, airflow: int) -> None:
        """Set the target airflow."""

        max_airflow = self._require_max_airflow()
        if (
            isinstance(airflow, bool)
            or not isinstance(airflow, int)
            or not 0 <= airflow <= max_airflow
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="value_out_of_range",
                translation_placeholders={
                    "value": str(airflow),
                    "minimum": "0",
                    "maximum": str(max_airflow),
                },
            )

        level = self._select_airflow_level(airflow)
        await self._set_airflow_for_level(level, airflow)
        await self._async_write_level(str(level))

    async def async_set_level(
        self,
        level: int,
    ) -> None:
        """Set ventilation level."""

        if level not in (0, 1, 2, 3):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_ventilation_level",
                translation_placeholders={"level": str(level)},
            )

        await self._async_write_level(str(level))

    async def _set_airflow_for_level(
        self,
        level: int,
        airflow: int,
    ) -> None:
        """Set airflow for a ventilation level."""

        device = self._device
        if device is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_unavailable",
            )

        parameters = device.parameters

        parameter = parameters.get(
            f"ventilation_mode_{level}_airflow"
        )

        if (
            not isinstance(parameter, dict)
            or not self._is_airflow_writable(parameter)
            or parameter.get("value_id") is None
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="airflow_parameter_unavailable",
                translation_placeholders={"level": str(level)},
            )

        limits = self._validated_airflow_bounds(parameter)
        if limits is None or not limits[0] <= airflow <= limits[1]:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="airflow_parameter_unavailable",
                translation_placeholders={"level": str(level)},
            )

        value_id = parameter["value_id"]
        if isinstance(value_id, bool) or not isinstance(value_id, (int, str)):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="airflow_parameter_unavailable",
                translation_placeholders={"level": str(level)},
            )
        try:
            numeric_value_id = int(value_id)
        except (TypeError, ValueError, OverflowError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="airflow_parameter_unavailable",
                translation_placeholders={"level": str(level)},
            ) from err
        if numeric_value_id <= 0:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="airflow_parameter_unavailable",
                translation_placeholders={"level": str(level)},
            )

        params = [(numeric_value_id, str(airflow))]

        _LOGGER.debug(
            "Writing airflow params: %s",
            params,
        )

        await self.client.write_parameters(
            self.system_id,
            params,
        )

        parameter["value"] = str(airflow)

        self.coordinator.async_set_updated_data(
            dict(self.coordinator.data)
        )
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

        _LOGGER.debug(
            "Ventilation level=%s airflow=%s",
            level,
            airflow,
        )

    async def _async_write_level(self, level_value: str) -> None:
        ventilation = self.data
        if ventilation is None or ventilation.get("value_id") is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="ventilation_parameter_unavailable",
            )

        params = []
        # mode = self._operating_mode
        mode = self._parameters.get(PARAM_OPERATING_MODE)

        if (
            isinstance(mode, dict)
            and mode.get("value_id") is not None
        ):
            _LOGGER.debug(
                "Switching operating mode to manual due to fan speed change"
            )
            params.append((int(mode["value_id"]), MODE_MANUAL_VALUE))
        params.append((int(ventilation["value_id"]), level_value))

        _LOGGER.debug(
            "Writing fan params: %s",
            params,
        )

        await self.client.write_parameters(self.system_id, params)
        ventilation["value"] = level_value
        if mode is not None:
            mode["value"] = MODE_MANUAL_VALUE
        self.coordinator.async_set_updated_data(dict(self.coordinator.data))
        await self.coordinator.async_request_refresh()

        _LOGGER.debug(
            "Operating mode=%s ventilation=%s",
            mode.get("value") if mode else None,
            ventilation.get("value"),
        )

    @property
    def preset_modes(self) -> list[str]:
        """Return available preset modes."""
        return list(FAN_PRESET_MODES)

    @property
    def preset_mode(self) -> str | None:
        """Return the stable translation key of the current preset."""
        mode = self._operating_mode

        if mode is None:
            return None

        return OPERATING_MODE_LABELS.get(mode)

    async def async_set_preset_mode(
        self,
        preset_mode: str,
    ) -> None:
        """Set the preset mode."""
        mode = self._parameters.get(PARAM_OPERATING_MODE)

        if not isinstance(mode, dict) or mode.get("value_id") is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="operating_mode_unavailable",
            )

        selected_value = OPERATING_MODE_LABELS_REVERSE.get(
            preset_mode
        )

        if selected_value is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_preset_mode",
                translation_placeholders={"preset_mode": preset_mode},
            )

        await self.client.write_parameters(
            self.system_id,
            [(int(mode["value_id"]), selected_value)],
        )

        mode["value"] = selected_value

        await self.coordinator.async_request_refresh()

    @property
    def werkt_percentage(self) -> int | None:
        """Return the legacy airflow percentage using the current snapshot."""
        return self._airflow_percentage

    @property
    def supported_features(self) -> FanEntityFeature:
        """Return supported features."""
        return (
            FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether a known ventilation level is active."""
        level = self._ventilation_level
        return None if level is None else level != 0

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""
        _LOGGER.debug(
            "Setting fan percentage=%s preset_mode=%s",
            percentage,
            preset_mode,
        )

        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
            return

#        if percentage is None:
#            percentage = ranged_value_to_percentage(
#                SPEED_RANGE,
#                1,
#            )
#        await self.async_set_percentage(percentage)
        if percentage is None:
            await self._async_write_level("1")
            return

        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_write_level("0")

    @property
    def old_operating_mode(self) -> dict | None:
        """Return the operating mode parameter."""
        if self._device is None:
            return None

        return self._device.get(
            "parameters",
            {},
        ).get(PARAM_OPERATING_MODE)

    @property
    def _operating_mode(self) -> str | None:
        """Return the operating mode."""
        parameter = self._parameters.get(PARAM_OPERATING_MODE)

        if not isinstance(parameter, dict):
            return None

        value = parameter.get("value")

        return str(value) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return extra attributes, omitting airflow when the level is unknown."""

        attributes: dict[str, object] = {}

        param = self.data or {}

        attributes.update(
            {
                "key": str(self.entity_description.key),
                "translation_key": str(self.entity_description.translation_key),
                "name": str(param.get("name")),
                "raw_name": str(param.get("raw_name")),
                "value": str(param.get("value")),
                "numeric_id": str(param.get("numeric_id")),
                "value_id": str(param.get("value_id")),
                "list_items": param.get("list_items"),
                "component_id": str(param.get("component_id")),
            }
        )

        value_state = param.get("value_state")
        attributes["raw_value_state"] = value_state

        if isinstance(value_state, int):
            attributes["value_state"] = VALUE_STATE_MAP.get(value_state, "unknown")
        else:
            attributes["value_state"] = "unavailable"

        control_type = param.get("control_type")
        attributes["raw_control_type"] = control_type

        if isinstance(control_type, int):
            attributes["control_type"] = CONTROL_TYPE_MAP.get(control_type, "unknown")
        else:
            attributes["control_type"] = "unavailable"

        read_write = param.get("read_write")
        attributes["raw_read_write"] = read_write

        if isinstance(read_write, int):
            attributes["read_write"] = READ_WRITE_MAP.get(read_write, "unknown")
        else:
            attributes["read_write"] = "unavailable"

        device = self._device
        if device is None:
            return attributes

        parameters = device.parameters
        level = self._ventilation_level
        if level is not None:
            airflow_param = parameters.get(f"ventilation_mode_{level}_airflow")
            if isinstance(airflow_param, dict):
                attributes["airflow"] = airflow_param.get("value")
        airflow_setpoint = (
            parameters.get("supply_air_flow_setpoint", {})
            .get("value")
        )
        attributes["airflow_setpont"] = airflow_setpoint

        if param.get("default_value") is not None:
            attributes["default_value"] = str(param["default_value"])

        if param.get("options"):
            attributes["raw_options"] = [
                option.get("label")
                for option in param.get("options", [])
            ]

        # These attibutes are NOT available to a fan entity, if they do it should not be a fan entity
        for key in (
            "default_value",
            "unit_of_measure",
            "min_value",
            "max_value",
            "step_width",
        ):
            if (value := param.get(key)) is not None:
                attributes[key] = value

        return attributes


class BrinkHomeVentilationFanEntity(BrinkHomeBaseFanEntity):
    """Continuous airflow fan."""

    entity_description = VENTILATION_FAN_DESCRIPTION

    def __init__(
        self,
        client,
        coordinator,
        system_id: int,
    ) -> None:
        """Initialize the airflow fan."""
        super().__init__(
            client,
            coordinator,
            system_id,
        )

        self._attr_unique_id = (
            f"{DOMAIN}_{system_id}_{self.parameter_key}_ventilation"
        )

    @property
    def percentage_step(self) -> float:
        """Return percentage step."""
        return 1

    @property
    def percentage(self) -> int | None:
        """Return current fan percentage."""
        return self._airflow_percentage

    @property
    def is_on(self) -> bool | None:
        """Report positive airflow at ventilation level zero as running."""
        level = self._ventilation_level
        if level != 0:
            return super().is_on
        parameter = self._parameters.get("ventilation_mode_0_airflow")
        if not isinstance(parameter, dict):
            return None
        raw_airflow = parameter.get("value")
        if isinstance(raw_airflow, bool):
            return None
        try:
            airflow = float(raw_airflow)
        except (TypeError, ValueError, OverflowError):
            return None
        capacity = self._max_airflow
        if (
            capacity is None
            or not math.isfinite(airflow)
            or not 0 <= airflow <= capacity
        ):
            return None
        return airflow > 0

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed percentage."""
        max_airflow = self._require_max_airflow()
        if (
            isinstance(percentage, bool)
            or not isinstance(percentage, int)
            or not 0 <= percentage <= 100
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="value_out_of_range",
                translation_placeholders={
                    "value": str(percentage),
                    "minimum": "0",
                    "maximum": "100",
                },
            )
        target_airflow = round(percentage / 100 * max_airflow)
        level = self._select_airflow_level(target_airflow)

        _LOGGER.debug(
            "Requested percentage=%s target_airflow=%s level=%s",
            percentage,
            target_airflow,
            level,
        )

        await self._set_airflow_for_level(
            level=level,
            airflow=target_airflow,
        )

        await self._async_write_level(str(level))

    async def async_turn_off(self, **kwargs) -> None:
        """Zero the level-zero airflow setting when switching this fan off."""
        await self._set_airflow_for_level(0, 0)
        await self._async_write_level("0")


class BrinkHomeLevelFanEntity(BrinkHomeBaseFanEntity):
    """Discrete level fan."""

    entity_description = FAN_DESCRIPTION

    def __init__(
        self,
        client,
        coordinator,
        system_id: int,
    ) -> None:
        """Initialize the level fan."""
        super().__init__(
            client,
            coordinator,
            system_id,
        )

        self._attr_unique_id = (
            f"{DOMAIN}_{system_id}_{self.parameter_key}_fan"
        )

    @property
    def speed_count(self) -> int:
        """Return the number of supported speeds."""
        return int_states_in_range(SPEED_RANGE)

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        current_value = self._ventilation_level
        if current_value is None or current_value == 4:
            return None

        if current_value == 0:
            return 0

        return ranged_value_to_percentage(
            SPEED_RANGE,
            current_value,
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan percentage."""

        if percentage <= 0:
            await self._async_write_level("0")
            return

        target_level = math.ceil(
            percentage_to_ranged_value(SPEED_RANGE, percentage)
        )
        target_level = max(
            SPEED_RANGE[0],
            min(SPEED_RANGE[1], target_level),
        )
        _LOGGER.debug(
            "Setting fan percentage=%s level=%s",
            percentage,
            target_level,
        )
        await self._async_write_level(str(target_level))
