"""Number entities for Brink ventilation."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import IntEnum

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfRatio,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONTROL_TYPE_MAP,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    PARAM_BYPASS_HYSTERESIS,
    PARAM_BYPASS_TEMPERATURE,
    PARAM_CO2_SENSOR_1_MAX_PPM,
    PARAM_CO2_SENSOR_1_MIN_PPM,
    PARAM_CO2_SENSOR_2_MAX_PPM,
    PARAM_CO2_SENSOR_2_MIN_PPM,
    PARAM_CO2_SENSOR_3_MAX_PPM,
    PARAM_CO2_SENSOR_3_MIN_PPM,
    PARAM_CO2_SENSOR_4_MAX_PPM,
    PARAM_CO2_SENSOR_4_MIN_PPM,
    PARAM_DAYS_UNTIL_FILTER_MESSAGE,
    PARAM_IMBALANCE_FIREPLACE,
    PARAM_MINIMUM_INTAKE_TEMPERATURE,
    PARAM_RH_SENSOR_SENSITIVITY,
    PARAM_SWITCH_TEMP_1,
    PARAM_SWITCH_TEMP_2,
    PARAM_VENTILATION_MODE_0,
    PARAM_VENTILATION_MODE_1,
    PARAM_VENTILATION_MODE_2,
    PARAM_VENTILATION_MODE_3,
    READ_WRITE_MAP,
    VALUE_STATE_MAP,
)
from .core.parameter_validation import (
    finite_parameter_bounds,
    redacted_parameter_attributes,
    writable_value_id,
)
from .entity import BrinkHomeDeviceEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class BrinkNumberEntityDescription(NumberEntityDescription):
    """Describe a Brink number entity."""

    parameter_key: str
    mode: NumberMode = NumberMode.AUTO


NUMBER_DESCRIPTIONS: tuple[BrinkNumberEntityDescription, ...] = (
    BrinkNumberEntityDescription(
        key="ventilation_mode_0_airflow",
        translation_key="ventilation_mode_0_airflow",
        parameter_key=PARAM_VENTILATION_MODE_0,
        mode=NumberMode.SLIDER,
        icon="mdi:fan-off",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        device_class=NumberDeviceClass.VOLUME_FLOW_RATE,
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkNumberEntityDescription(
        key="ventilation_mode_1_airflow",
        translation_key="ventilation_mode_1_airflow",
        parameter_key=PARAM_VENTILATION_MODE_1,
        mode=NumberMode.SLIDER,
        icon="mdi:fan-speed-1",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        device_class=NumberDeviceClass.VOLUME_FLOW_RATE,
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkNumberEntityDescription(
        key="ventilation_mode_2_airflow",
        translation_key="ventilation_mode_2_airflow",
        parameter_key=PARAM_VENTILATION_MODE_2,
        mode=NumberMode.SLIDER,
        icon="mdi:fan-speed-2",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        device_class=NumberDeviceClass.VOLUME_FLOW_RATE,
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkNumberEntityDescription(
        key="ventilation_mode_3_airflow",
        translation_key="ventilation_mode_3_airflow",
        parameter_key=PARAM_VENTILATION_MODE_3,
        mode=NumberMode.SLIDER,
        icon="mdi:fan-speed-3",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        device_class=NumberDeviceClass.VOLUME_FLOW_RATE,
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkNumberEntityDescription(
        key="switch_temp_1",
        translation_key="switch_temp_1",
        parameter_key=PARAM_SWITCH_TEMP_1,
        mode=NumberMode.SLIDER,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:thermometer-low",
    ),
    BrinkNumberEntityDescription(
        key="switch_temp_2",
        translation_key="switch_temp_2",
        parameter_key=PARAM_SWITCH_TEMP_2,
        mode=NumberMode.SLIDER,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:thermometer-high",
    ),
    BrinkNumberEntityDescription(
        key="bypass_temperature",
        translation_key="bypass_temperature",
        parameter_key=PARAM_BYPASS_TEMPERATURE,
        mode=NumberMode.SLIDER,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:thermometer-chevron-up",
    ),
    BrinkNumberEntityDescription(
        key="bypass_hysteresis",
        translation_key="bypass_hysteresis",
        parameter_key=PARAM_BYPASS_HYSTERESIS,
        mode=NumberMode.SLIDER,
        native_min_value=0.0,
        native_max_value=5.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:thermometer-lines",
    ),
    BrinkNumberEntityDescription(
        key="minimum_intake_temperature",
        translation_key="minimum_intake_temperature",
        parameter_key=PARAM_MINIMUM_INTAKE_TEMPERATURE,
        mode=NumberMode.SLIDER,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:thermometer-low",
    ),
    BrinkNumberEntityDescription(
        key="maximum_intake_temperature",
        translation_key="maximum_intake_temperature",
        parameter_key="maximum_intake_temperature",
        mode=NumberMode.SLIDER,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:thermometer-low",
    ),
    BrinkNumberEntityDescription(
        key="days_until_filter_message",
        translation_key="days_until_filter_message",
        parameter_key=PARAM_DAYS_UNTIL_FILTER_MESSAGE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:air-filter",
    ),
    BrinkNumberEntityDescription(
        key="v1_minimum_voltage",
        translation_key="v1_minimum_voltage",
        parameter_key="v1_minimum_voltage",
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=NumberDeviceClass.VOLTAGE,
        icon="mdi:current-dc",
    ),
    BrinkNumberEntityDescription(
        key="v1_maximum_voltage",
        translation_key="v1_maximum_voltage",
        parameter_key="v1_maximum_voltage",
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=NumberDeviceClass.VOLTAGE,
        icon="mdi:current-dc",
    ),
    BrinkNumberEntityDescription(
        key="v2_minimum_voltage",
        translation_key="v2_minimum_voltage",
        parameter_key="v2_minimum_voltage",
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=NumberDeviceClass.VOLTAGE,
        icon="mdi:current-dc",
    ),
    BrinkNumberEntityDescription(
        key="v2_maximum_voltage",
        translation_key="v2_maximum_voltage",
        parameter_key="v2_maximum_voltage",
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=NumberDeviceClass.VOLTAGE,
        icon="mdi:current-dc",
    ),
    BrinkNumberEntityDescription(
        key="imbalance_fireplace",
        translation_key="imbalance_fireplace",
        parameter_key=PARAM_IMBALANCE_FIREPLACE,
        mode=NumberMode.SLIDER,
        native_min_value=0,
        native_max_value=20,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:fire",
    ),
    BrinkNumberEntityDescription(
        key="rh_sensor_sensitivity",
        translation_key="rh_sensor_sensitivity",
        parameter_key=PARAM_RH_SENSOR_SENSITIVITY,
        mode=NumberMode.SLIDER,
        native_min_value=-2,
        native_max_value=2,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:water-percent",
    ),
    BrinkNumberEntityDescription(
        key="co2_sensor_1_min_ppm",
        translation_key="co2_sensor_1_min_ppm",
        parameter_key=PARAM_CO2_SENSOR_1_MIN_PPM,
        mode=NumberMode.BOX,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        device_class=NumberDeviceClass.CO2,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:molecule-co2",
        entity_registry_enabled_default=False,
    ),
    BrinkNumberEntityDescription(
        key="co2_sensor_1_max_ppm",
        translation_key="co2_sensor_1_max_ppm",
        parameter_key=PARAM_CO2_SENSOR_1_MAX_PPM,
        mode=NumberMode.BOX,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        device_class=NumberDeviceClass.CO2,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:molecule-co2",
        entity_registry_enabled_default=False,
    ),
    BrinkNumberEntityDescription(
        key="co2_sensor_2_min_ppm",
        translation_key="co2_sensor_2_min_ppm",
        parameter_key=PARAM_CO2_SENSOR_2_MIN_PPM,
        mode=NumberMode.BOX,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        device_class=NumberDeviceClass.CO2,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:molecule-co2",
        entity_registry_enabled_default=False,
    ),
    BrinkNumberEntityDescription(
        key="co2_sensor_2_max_ppm",
        translation_key="co2_sensor_2_max_ppm",
        parameter_key=PARAM_CO2_SENSOR_2_MAX_PPM,
        mode=NumberMode.BOX,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        device_class=NumberDeviceClass.CO2,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:molecule-co2",
        entity_registry_enabled_default=False,
    ),
    BrinkNumberEntityDescription(
        key="co2_sensor_3_min_ppm",
        translation_key="co2_sensor_3_min_ppm",
        parameter_key=PARAM_CO2_SENSOR_3_MIN_PPM,
        mode=NumberMode.BOX,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        device_class=NumberDeviceClass.CO2,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:molecule-co2",
        entity_registry_enabled_default=False,
    ),
    BrinkNumberEntityDescription(
        key="co2_sensor_3_max_ppm",
        translation_key="co2_sensor_3_max_ppm",
        parameter_key=PARAM_CO2_SENSOR_3_MAX_PPM,
        mode=NumberMode.BOX,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        device_class=NumberDeviceClass.CO2,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:molecule-co2",
        entity_registry_enabled_default=False,
    ),
    BrinkNumberEntityDescription(
        key="co2_sensor_4_min_ppm",
        translation_key="co2_sensor_4_min_ppm",
        parameter_key=PARAM_CO2_SENSOR_4_MIN_PPM,
        mode=NumberMode.BOX,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        device_class=NumberDeviceClass.CO2,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:molecule-co2",
        entity_registry_enabled_default=False,
    ),
    BrinkNumberEntityDescription(
        key="co2_sensor_4_max_ppm",
        translation_key="co2_sensor_4_max_ppm",
        parameter_key=PARAM_CO2_SENSOR_4_MAX_PPM,
        mode=NumberMode.BOX,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        device_class=NumberDeviceClass.CO2,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:molecule-co2",
        entity_registry_enabled_default=False,
    ),
)


class ValueState(IntEnum):
    """Represents the state of a sensor value."""
    INVALID = 5


class BrinkHomeNumberEntity(BrinkHomeDeviceEntity, NumberEntity):
    """Representation of a Brink number."""

    _attr_has_entity_name = True

    entity_description: BrinkNumberEntityDescription

    def __init__(
        self,
        client,
        coordinator,
        system_id: int,
        description: BrinkNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(
            client,
            coordinator,
            system_id,
            description.parameter_key,
        )
        self.entity_description = description

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.system_id}_{self.parameter_key}_number"

    @property
    def native_value(self) -> int | float | None:
        """Return the current value."""
        param = self.data

        if param is None:
            return None

        value = param.get("value")

        if value is None:
            return None

        try:
            numeric_value = float(value)

            return (
                int(numeric_value)
                if int(param.get("decimals", 0)) == 0
                else numeric_value
            )
        except (TypeError, ValueError):
            return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement."""
        if (
            self.entity_description.native_unit_of_measurement
            is not None
        ):
            return str(
                self.entity_description.native_unit_of_measurement
            )

        param = self.data

        if param is None:
            return None

        unit = param.get("unit_of_measure")

        if not unit:
            return None

        return str(unit)

    @property
    def native_default_value(self) -> float | None:
        """Return the default value."""
        param = self.data

        if param is None:
            return None

        default_value = param.get("default_value")

        if default_value is None:
            default_value = param.get("min_value")

        if default_value is None:
            return None

        try:
            numeric_value = float(default_value)

            if int(param.get("decimals", 0)) == 0:
                return int(numeric_value)

            return numeric_value
        except (TypeError, ValueError):
            return None

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        param = self.data

        if param is None:
            return self.entity_description.native_min_value or 0

        try:
            min_value = param.get("min_value")

            if min_value is not None:
                return float(min_value)

        except (TypeError, ValueError):
            pass

        return self.entity_description.native_min_value or 0

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        param = self.data

        if param is None:
            return self.entity_description.native_max_value or 100

        try:
            max_value = param.get("max_value")

            if max_value is not None:
                return float(max_value)

        except (TypeError, ValueError):
            pass

        return self.entity_description.native_max_value or 100

    @property
    def native_step(self) -> float:
        """Return the step size."""
        param = self.data

        if param is None:
            return 1.0

        step_width = param.get("step_width")
        if step_width is None:
            return 1.0

        try:
            step_width = param.get("step_width")

            if step_width is not None:
                return float(step_width)

            decimals = int(param.get("decimals", 0))

            if decimals > 0:
                return 10**-decimals

        except (TypeError, ValueError):
            pass

        return 1.0

    @property
    def available(self) -> bool:
        """Return if entity is available."""

        device = self._device
        if device is None:
            return False

        parameters = device.parameters

        param = self.data

        if (
            param is None
            or param.get("value_state") == ValueState.INVALID
        ):
            _LOGGER.debug(
                "Brink number parameter unavailable: key=%s",
                self.entity_description.parameter_key,
            )

        if self.entity_description.parameter_key == "ventilation_percentage":
            return True

        if self.entity_description.parameter_key == "gateway_state":
            return True

        if (
            "co2_sensor_" in self.entity_description.parameter_key
            or self.entity_description.parameter_key == "rh_sensor_sensitivity"
        ):
            sensor_status = parameters.get("ebus_co2_sensor_status")
            if not isinstance(sensor_status, dict):
                return False
            raw_status = sensor_status.get("value")
            if isinstance(raw_status, bool) or not isinstance(raw_status, (int, str)):
                return False
            try:
                if int(raw_status) != 1:
                    return False
            except (TypeError, ValueError, OverflowError):
                return False

        return (
            super().available
            and param is not None
            and param.get("value_state") != ValueState.INVALID
        )

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return extra state attributes."""

        # Get base attributes
        attributes: dict[str, object] = {}

        param = self.data or {}

        attributes = {
            "key": str(self.entity_description.key),
            "translation_key": str(self.entity_description.translation_key),
            "name": str(param.get("name")),
            "raw_name": str(param.get("raw_name")),
            "value": str(param.get("value")),
            "decimals": str(param.get("decimals")),
            "numeric_id": str(param.get("numeric_id")),
            "value_id": str(param.get("value_id")),
            "component_id": str(param.get("component_id")),
            "raw_options": param.get("options"),
            "default_value": str(param.get("default_value")),
            "min_value": str(param.get("min_value")),
            "max_value": str(param.get("max_value")),
            "step_width": str(param.get("step_width")),
            "unit_of_measure": str(param.get("unit_of_measure")),
        }

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

        if param.get("options") != []:
            attributes["raw_options"] = param.get("options")

        if param.get("list_items") != []:
            attributes["list_items"] = param.get("list_items")

        return redacted_parameter_attributes(attributes)

    async def async_set_native_value(self, value: float) -> None:
        """Set the airflow value."""
        param = self.data
        value_id = writable_value_id(param)
        bounds = finite_parameter_bounds(param)
        if value_id is None or bounds is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="parameter_unavailable",
                translation_placeholders={"parameter": self.parameter_name},
            )

        min_value, max_value = bounds
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not min_value <= value <= max_value
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="value_out_of_range",
                translation_placeholders={
                    "value": str(value),
                    "minimum": str(min_value),
                    "maximum": str(max_value),
                },
            )

        raw_decimals = param.get("decimals", 0)
        if isinstance(raw_decimals, bool):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="parameter_unavailable",
                translation_placeholders={"parameter": self.parameter_name},
            )
        try:
            decimals = int(raw_decimals)
        except (TypeError, ValueError, OverflowError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="parameter_unavailable",
                translation_placeholders={"parameter": self.parameter_name},
            ) from err
        if not 0 <= decimals <= 6:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="parameter_unavailable",
                translation_placeholders={"parameter": self.parameter_name},
            )
        new_value = (
            f"{value:.{decimals}f}" if decimals > 0 else str(int(round(value)))
        )

        await self.client.write_parameters(
            self.system_id,
            [(value_id, new_value)],
        )

        param["value"] = new_value

        self.coordinator.async_set_updated_data(
            dict(self.coordinator.data)
        )
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the Brink select platform."""
    client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities = [
        BrinkHomeNumberEntity(
            client,
            coordinator,
            system_id,
            description,
        )
        for system_id, device in (coordinator.data or {}).items()
        for description in NUMBER_DESCRIPTIONS
        if device.parameters.get(description.parameter_key)
    ]

    async_add_entities(entities)
