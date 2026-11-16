from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import IntEnum
from types import MappingProxyType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfPressure,
    UnitOfRatio,
    UnitOfSoundPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import StateType
from homeassistant.util import slugify

from .const import (
    ACTIVE_CONTROL_STATUS_LABELS,
    BYPASS_VALVE_STATUS_LABELS,
    CONTROL_TYPE_MAP,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    FROST_PROTECTION_STATUS_LABELS,
    GATEWAY_STATE_LABELS,
    GEOTHERMAL_HEAT_EXCHANGER_LABELS,
    PARAM_ACTIVE_CONTROL_STATUS,
    PARAM_ACTUAL_SUPPLY_AIR_FLOW,
    PARAM_BYPASS_VALVE_STATUS,
    PARAM_CO2_SENSOR_1,
    PARAM_CO2_SENSOR_2,
    PARAM_CO2_SENSOR_3,
    PARAM_CO2_SENSOR_4,
    PARAM_DAYS_SINCE_FILTER_RESET,
    PARAM_DAYS_UNTIL_FILTER_MESSAGE,
    PARAM_EXHAUST_AIR_FLOW,
    PARAM_EXHAUST_AIR_PRESSURE,
    PARAM_EXHAUST_TEMP,
    PARAM_FRESH_AIR_TEMP,
    PARAM_FROST_PROTECTION_STATUS,
    PARAM_HUMIDITY,
    PARAM_NOMINAL_EXHAUST_AIR_FLOW,
    PARAM_NOMINAL_SUPPLY_AIR_FLOW,
    PARAM_PREHEATER_POWER,
    PARAM_PREHEATER_STATUS,
    PARAM_REMAINING_DURATION,
    PARAM_STATUS_GEOTHERMAL_HEAT_EXCHANGER,
    PARAM_SUPPLY_AIR_FLOW,
    PARAM_SUPPLY_AIR_PRESSURE,
    PARAM_SUPPLY_TEMP,
    PARAM_VENTILATION_MODE_0,
    PARAM_VENTILATION_MODE_1,
    PARAM_VENTILATION_MODE_2,
    PARAM_VENTILATION_MODE_3,
    PREHEATER_STATUS_LABELS,
    READ_WRITE_MAP,
    VALUE_STATE_MAP,
    VENTILATION_LEVEL_LABELS,
)
from .core.parameter_validation import redacted_parameter_attributes
from .entity import BrinkHomeDeviceEntity
from .sound import (
    CABINET_SOUND_POWER_COEFFICIENTS,
    EXHAUST_SOUND_POWER_COEFFICIENTS,
    SUPPLY_SOUND_POWER_COEFFICIENTS,
    estimate_sound_power,
)

_LOGGER = logging.getLogger(__name__)


class ValueState(IntEnum):
    """Represents the state of a sensor value."""
    INVALID = 5


# @dataclass(frozen=True)
@dataclass(slots=True, frozen=True, kw_only=True)
class BrinkSensorDescription(SensorEntityDescription):
    """Describe a Brink sensor entity."""

    parameter_key: str
    is_enum: bool = False
    is_device_attribute: bool = False
    required_value_state: int | None = None
    # value_map: dict[int, str] | None = None
    value_map: Mapping[int, str] | None = None
    enabled_value_state: int | None = None
    # _attr_has_entity_name = True
    value_fn: Callable[[BrinkHomeSensorEntity], StateType | None] | None = None
    attr_fn: Callable[[BrinkHomeSensorEntity], Mapping[str, object] | None] | None = None

    @property
    def slugified_value_map(self) -> Mapping[int, str]:
        """Return immutable translation keys cached per sensor description."""
        try:
            return object.__getattribute__(self, "_slugified_value_map_cache")
        except AttributeError:
            slugified = (
                {value: slugify(label) for value, label in self.value_map.items()}
                if self.value_map
                else {}
            )
            cached_mapping = MappingProxyType(slugified)
            object.__setattr__(self, "_slugified_value_map_cache", cached_mapping)
            return cached_mapping

    @property
    def slugified_options(self) -> tuple[str, ...]:
        """Return immutable enum options derived from the cached value map."""
        try:
            return object.__getattribute__(self, "_slugified_options_cache")
        except AttributeError:
            options = tuple(self.slugified_value_map.values())
            object.__setattr__(self, "_slugified_options_cache", options)
            return options


SENSOR_DESCRIPTIONS: tuple[BrinkSensorDescription, ...] = (
    BrinkSensorDescription(
        key="ventilation_level",
        translation_key="ventilation_level",
        parameter_key="ventilation_level",
        icon="mdi:fan",
        device_class=SensorDeviceClass.ENUM,
        is_enum=True,
        value_map=VENTILATION_LEVEL_LABELS
    ),
    BrinkSensorDescription(
        key=PARAM_SUPPLY_AIR_FLOW,
        translation_key="actual_supply_air_flow",
        parameter_key=PARAM_SUPPLY_AIR_FLOW,
        icon="mdi:fan-chevron-up",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE
    ),
    BrinkSensorDescription(
        key=PARAM_ACTUAL_SUPPLY_AIR_FLOW,
        translation_key="actual_supply_air_flow",
        parameter_key=PARAM_ACTUAL_SUPPLY_AIR_FLOW,
        icon="mdi:fan-chevron-up",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE
    ),
    BrinkSensorDescription(
        key=PARAM_EXHAUST_AIR_FLOW,
        translation_key="actual_exhaust_air_flow",
        parameter_key=PARAM_EXHAUST_AIR_FLOW,
        icon="mdi:fan-chevron-down",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE
    ),
    BrinkSensorDescription(
        key=PARAM_NOMINAL_SUPPLY_AIR_FLOW,
        translation_key="nominal_supply_air_flow",
        parameter_key=PARAM_NOMINAL_SUPPLY_AIR_FLOW,
        icon="mdi:fan-chevron-up",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE
    ),
    BrinkSensorDescription(
        key=PARAM_NOMINAL_EXHAUST_AIR_FLOW,
        translation_key="nominal_exhaust_air_flow",
        parameter_key=PARAM_NOMINAL_EXHAUST_AIR_FLOW,
        icon="mdi:fan-chevron-down",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE
    ),
    BrinkSensorDescription(
        key=PARAM_FRESH_AIR_TEMP,
        translation_key="fresh_air_temp",
        parameter_key=PARAM_FRESH_AIR_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key="extract_air_temperature",
        translation_key="extract_air_temperature",
        parameter_key="extract_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key=PARAM_EXHAUST_TEMP,
        translation_key="exhaust_temp",
        parameter_key=PARAM_EXHAUST_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key=PARAM_SUPPLY_TEMP,
        translation_key="supply_temp",
        parameter_key=PARAM_SUPPLY_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key=PARAM_HUMIDITY,
        translation_key="humidity",
        parameter_key=PARAM_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        required_value_state=1,
    ),
    BrinkSensorDescription(
        key="supply_air_humidity",
        translation_key="supply_air_humidity",
        parameter_key="supply_air_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key="extract_air_humidity",
        translation_key="extract_air_humidity",
        parameter_key="extract_air_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key="relative_humidity",
        translation_key="relative_humidity",
        parameter_key="relative_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        required_value_state=1,
    ),
    BrinkSensorDescription(
        key=PARAM_DAYS_SINCE_FILTER_RESET,
        translation_key="days_since_filter_reset",
        parameter_key=PARAM_DAYS_SINCE_FILTER_RESET,
        icon="mdi:air-filter",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key=PARAM_DAYS_UNTIL_FILTER_MESSAGE,
        translation_key="days_until_filter_message",
        parameter_key=PARAM_DAYS_UNTIL_FILTER_MESSAGE,
        icon="mdi:air-filter",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key=PARAM_REMAINING_DURATION,
        translation_key="remaining_duration",
        parameter_key=PARAM_REMAINING_DURATION,
        icon="mdi:timer-sand",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key=PARAM_ACTIVE_CONTROL_STATUS,
        translation_key="active_control_status",
        parameter_key=PARAM_ACTIVE_CONTROL_STATUS,
        icon="mdi:tune",
        device_class=SensorDeviceClass.ENUM,
        is_enum=True,
        value_map=ACTIVE_CONTROL_STATUS_LABELS,
        entity_registry_enabled_default=True,
    ),
    BrinkSensorDescription(
        key=PARAM_PREHEATER_STATUS,
        translation_key="preheater_status",
        parameter_key=PARAM_PREHEATER_STATUS,
        icon="mdi:radiator",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_enum=True,
        required_value_state=1,
        value_map=PREHEATER_STATUS_LABELS,
    ),
    BrinkSensorDescription(
        key=PARAM_BYPASS_VALVE_STATUS,
        translation_key="bypass_valve_status",
        parameter_key=PARAM_BYPASS_VALVE_STATUS,
        icon="mdi:call-split",
        device_class=SensorDeviceClass.ENUM,
        is_enum=True,
        value_map=BYPASS_VALVE_STATUS_LABELS,
    ),
    BrinkSensorDescription(
        key=PARAM_CO2_SENSOR_1,
        translation_key="co2_sensor_1",
        parameter_key=PARAM_CO2_SENSOR_1,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_value_state=1,
        icon="mdi:molecule-co2",
        entity_registry_enabled_default=False,
    ),
    BrinkSensorDescription(
        key=PARAM_CO2_SENSOR_2,
        translation_key="co2_sensor_2",
        parameter_key=PARAM_CO2_SENSOR_2,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_value_state=1,
        icon="mdi:molecule-co2",
        entity_registry_enabled_default=False,
    ),
    BrinkSensorDescription(
        key=PARAM_CO2_SENSOR_3,
        translation_key="co2_sensor_3",
        parameter_key=PARAM_CO2_SENSOR_3,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_value_state=1,
        icon="mdi:molecule-co2",
        entity_registry_enabled_default=False,
    ),
    BrinkSensorDescription(
        key=PARAM_CO2_SENSOR_4,
        translation_key="co2_sensor_4",
        parameter_key=PARAM_CO2_SENSOR_4,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_value_state=1,
        icon="mdi:molecule-co2",
        entity_registry_enabled_default=False,
    ),
    BrinkSensorDescription(
        key="extra_air_temp",
        translation_key="extra_air_temp",
        parameter_key="extra_air_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        entity_registry_enabled_default=False,
    ),
    BrinkSensorDescription(
        key="additional_temperature_sensor",
        translation_key="additional_temperature_sensor",
        parameter_key="additional_temperature_sensor",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        entity_registry_enabled_default=False,
    ),
    BrinkSensorDescription(
        key=PARAM_FROST_PROTECTION_STATUS,
        translation_key="frost_protection_status",
        parameter_key=PARAM_FROST_PROTECTION_STATUS,
        icon="mdi:snowflake-alert",
        device_class=SensorDeviceClass.ENUM,
        is_enum=True,
        value_map=FROST_PROTECTION_STATUS_LABELS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key=PARAM_STATUS_GEOTHERMAL_HEAT_EXCHANGER,
        translation_key="status_geothermal_heat_exchanger",
        parameter_key=PARAM_STATUS_GEOTHERMAL_HEAT_EXCHANGER,
        icon="mdi:heat-pump",
        device_class=SensorDeviceClass.ENUM,
        is_enum=True,
        value_map=GEOTHERMAL_HEAT_EXCHANGER_LABELS,
    ),
    BrinkSensorDescription(
        key="analog_input_1",
        translation_key="analog_input_1",
        parameter_key="analog_input_1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sine-wave",
    ),
    BrinkSensorDescription(
        key="analog_input_2",
        translation_key="analog_input_2",
        parameter_key="analog_input_2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sine-wave",
    ),
    BrinkSensorDescription(
        key="supply_air_pressure",
        translation_key="supply_air_pressure",
        parameter_key=PARAM_SUPPLY_AIR_PRESSURE,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key="exhaust_air_pressure",
        translation_key="exhaust_air_pressure",
        parameter_key=PARAM_EXHAUST_AIR_PRESSURE,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key="supply_air_flow_setpoint",
        translation_key="supply_air_flow_setpoint",
        parameter_key="supply_air_flow_setpoint",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        icon="mdi:fan-chevron-up",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="exhaust_air_flow_setpoint",
        translation_key="exhaust_air_flow_setpoint",
        parameter_key="exhaust_air_flow_setpoint",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        icon="mdi:fan-chevron-down",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="nominal_supply_air_flow",
        translation_key="nominal_supply_air_flow",
        parameter_key="nominal_supply_air_flow",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        icon="mdi:fan-chevron-down",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="nominal_exhaust_air_flow",
        translation_key="nominal_exhaust_air_flow",
        parameter_key="nominal_exhaust_air_flow",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        icon="mdi:fan-chevron-up",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="ventilation_percentage",
        translation_key="ventilation_percentage",
        parameter_key="ventilation_percentage",
        icon="mdi:fan",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key="v1_analog_input",
        translation_key="v1_analog_input",
        parameter_key="v1_analog_input",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sine-wave",
    ),
    BrinkSensorDescription(
        key="v2_analog_input",
        translation_key="v2_analog_input",
        parameter_key="v2_analog_input",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sine-wave",
    ),
    BrinkSensorDescription(
        key="ventilation_mode_0_airflow",
        translation_key="ventilation_mode_0_airflow",
        parameter_key=PARAM_VENTILATION_MODE_0,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        icon="mdi:fan-off",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="ventilation_mode_1_airflow",
        translation_key="ventilation_mode_1_airflow",
        parameter_key=PARAM_VENTILATION_MODE_1,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        icon="mdi:fan-speed-1",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="ventilation_mode_2_airflow",
        translation_key="ventilation_mode_2_airflow",
        parameter_key=PARAM_VENTILATION_MODE_2,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        icon="mdi:fan-speed-2",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="ventilation_mode_3_airflow",
        translation_key="ventilation_mode_3_airflow",
        parameter_key=PARAM_VENTILATION_MODE_3,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        icon="mdi:fan-speed-3",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="supply_duct_pressure",
        translation_key="supply_duct_pressure",
        parameter_key="supply_duct_pressure",
        native_unit_of_measurement=UnitOfPressure.PA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="exhaust_duct_pressure",
        translation_key="exhaust_duct_pressure",
        parameter_key="exhaust_duct_pressure",
        native_unit_of_measurement=UnitOfPressure.PA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="supply_fan_rpm",
        translation_key="supply_fan_rpm",
        parameter_key="supply_fan_rpm",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:fan",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="exhaust_fan_rpm",
        translation_key="exhaust_fan_rpm",
        parameter_key="exhaust_fan_rpm",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:fan",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="preheater_power",
        translation_key="preheater_power",
        parameter_key=PARAM_PREHEATER_POWER,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:radiator",
        entity_registry_enabled_default=False,
    ),
    BrinkSensorDescription(
        key="gateway_state",
        translation_key="gateway_state",
        parameter_key="gateway_state",
        icon="mdi:lan",
        device_class=SensorDeviceClass.ENUM,
        options=list(GATEWAY_STATE_LABELS.values()),
        is_enum=True,
        is_device_attribute=True,
        value_map=GATEWAY_STATE_LABELS,
    ),
    BrinkSensorDescription(
        key="ip_address",
        translation_key="ip_address",
        parameter_key="ip_address",
        icon="mdi:lan",
        is_device_attribute=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="owner_group_name",
        translation_key="owner_group_name",
        parameter_key="owner_group_name",
        icon="mdi:account-group",
        is_device_attribute=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="iana_time_zone",
        translation_key="iana_time_zone",
        parameter_key="iana_time_zone",
        icon="mdi:clock-time-four-outline",
        is_device_attribute=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="two_letter_country_code",
        translation_key="two_letter_country_code",
        parameter_key="two_letter_country_code",
        icon="mdi:flag-outline",
        is_device_attribute=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="active_alert_count",
        translation_key="active_alert_count",
        parameter_key="active_alert_count",
        icon="mdi:alert-circle-outline",
        is_device_attribute=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key="access_level",
        translation_key="access_level",
        parameter_key="access_level",
        icon="mdi:shield-account-outline",
        is_device_attribute=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="dns_server",
        translation_key="dns_server",
        parameter_key="dns_server",
        icon="mdi:lan",
        is_device_attribute=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="cabinet_sound_power",
        translation_key="cabinet_sound_power",
        parameter_key="cabinet_sound_power",
        icon="mdi:speaker",
        native_unit_of_measurement=UnitOfSoundPressure.WEIGHTED_DECIBEL_A,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: entity.cabinet_sound_power,
        attr_fn=lambda entity: {
            "average_airflow": entity.cabinet_airflow,
            "average_pressure": entity.cabinet_pressure,
            "supply_airflow": entity.supply_airflow,
            "supply_pressure": entity.supply_pressure,
            "exhaust_airflow": entity.exhaust_airflow,
            "exhaust_pressure": entity.exhaust_pressure,
            "calculation": "2D second-order polynomial regression",
        },
    ),
    BrinkSensorDescription(
        key="supply_sound_power",
        translation_key="supply_sound_power",
        parameter_key="supply_sound_power",
        icon="mdi:speaker",
        native_unit_of_measurement=UnitOfSoundPressure.WEIGHTED_DECIBEL_A,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: entity.supply_sound_power,
        attr_fn=lambda entity: {
            "airflow": entity.supply_airflow,
            "pressure": entity.supply_pressure,
            "method": "2D polynomial regression",
        },
    ),
    BrinkSensorDescription(
        key="exhaust_sound_power",
        translation_key="exhaust_sound_power",
        parameter_key="exhaust_sound_power",
        icon="mdi:speaker",
        native_unit_of_measurement=UnitOfSoundPressure.WEIGHTED_DECIBEL_A,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: entity.exhaust_sound_power,
        attr_fn=lambda entity: {
            "airflow": entity.exhaust_airflow,
            "pressure": entity.exhaust_pressure,
            "method": "2D polynomial regression",
        },
    ),
)


def _should_create_sensor(device: dict, description: BrinkSensorDescription) -> bool:
    """Return True when the Brink parameter should be exposed as a sensor."""

    if description.parameter_key in {
        "ventilation_percentage",
        "cabinet_sound_power",
        "supply_sound_power",
        "exhaust_sound_power",
    }:
        return True

    if description.is_device_attribute:
        return True

    param = device.parameters.get(description.parameter_key)

    if not param:
        return False

    if param.get("value_state") == ValueState.INVALID:
        return False

    # CO2 sensors are only available when the value is not 0, otherwise they are not connected
    if description.parameter_key in {
        PARAM_CO2_SENSOR_1,
        PARAM_CO2_SENSOR_2,
        PARAM_CO2_SENSOR_3,
        PARAM_CO2_SENSOR_4,
    }:
        return str(param.get("value")) != "0"

    required_value_state = description.required_value_state
    if required_value_state is None:
        return True

    return param.get("value_state") == required_value_state


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the Brink sensor platform."""
    client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    known_parameters = {
        description.parameter_key
        for description in SENSOR_DESCRIPTIONS
    }

    known_parameters.add("supply_air_pressure")
    # device
    known_parameters.add("device_type")
    known_parameters.add("software_label")
    # fan
    known_parameters.add("ventilation_level")
    known_parameters.add("operating_mode")
    # select
    known_parameters.add("bypass_operation")
    known_parameters.add("signal_output_mode")

    known_parameters.add("contact_1_type")
    known_parameters.add("contact_2_type")

    known_parameters.add("cn1_switch_input_condition")
    known_parameters.add("cn2_switch_input_condition")

    known_parameters.add("contact_1_supply_fan_action")
    known_parameters.add("contact_1_exhaust_fan_action")
    known_parameters.add("contact_2_supply_fan_action")
    known_parameters.add("contact_2_exhaust_fan_action")

    known_parameters.add("mode_input_1")
    known_parameters.add("mode_input_2")

    known_parameters.add("mode_valve_24v_control")
    known_parameters.add("valve_control")
    known_parameters.add("rh_sensor_sensitivity")

    # number
    known_parameters.add("bypass_temperature")
    known_parameters.add("bypass_hysteresis")
    known_parameters.add("minimum_intake_temperature")
    known_parameters.add("imbalance_fireplace")
    known_parameters.add("v1_minimum_voltage")
    known_parameters.add("v1_maximum_voltage")
    known_parameters.add("v2_minimum_voltage")
    known_parameters.add("v2_maximum_voltage")
    known_parameters.add("switch_temp_1")
    known_parameters.add("switch_temp_2")

    known_parameters.add("co2_sensor_1_min_ppm")
    known_parameters.add("co2_sensor_1_max_ppm")
    known_parameters.add("co2_sensor_2_min_ppm")
    known_parameters.add("co2_sensor_2_max_ppm")
    known_parameters.add("co2_sensor_3_min_ppm")
    known_parameters.add("co2_sensor_3_max_ppm")
    known_parameters.add("co2_sensor_4_min_ppm")
    known_parameters.add("co2_sensor_4_max_ppm")

    # Binary
    known_parameters.add("cn1_switch_input")
    known_parameters.add("cn2_switch_input")

    known_parameters.add("rh_sensor_status")
    known_parameters.add("ebus_co2_sensor_status")

    unknown_count = sum(
        1
        for device in (coordinator.data or {}).values()
        for parameter_key in device.parameters
        if parameter_key not in known_parameters
    )
    if unknown_count:
        _LOGGER.debug("Brink has %s unknown parameter definitions", unknown_count)

    entities = [
        BrinkHomeSensorEntity(client, coordinator, system_id, description)
        for system_id, device in (coordinator.data or {}).items()
        for description in SENSOR_DESCRIPTIONS
        if _should_create_sensor(device, description)
    ]
    async_add_entities(entities)


class BrinkHomeSensorEntity(BrinkHomeDeviceEntity, SensorEntity):
    """Representation of a Brink sensor."""

    _attr_has_entity_name = True
    entity_description: BrinkSensorDescription

    def __init__(self, client, coordinator, system_id: int, description: BrinkSensorDescription):
        """Initialize the Brink sensor."""
        super().__init__(client, coordinator, system_id, description.parameter_key)
        self.entity_description = description

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.system_id}_{self.parameter_key}_sensor"

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return extra state attributes."""
        if self.entity_description.parameter_key == "ventilation_percentage":
            return {}

        # Get base attributes
        attributes: dict[str, object] = {}

        param = self.data or {}

        attributes = {
            "key": str(self.entity_description.key),
            "translation_key": str(self.entity_description.translation_key),
            "name": str(param.get("name")),
            "raw_name": str(param.get("raw_name")),
            "value": str(param.get("value")),
            "_raw_value": str(self._raw_value),
            "decimals": str(param.get("decimals")),
            "numeric_id": str(param.get("numeric_id")),
            "value_id": str(param.get("value_id")),
            "component_id": str(param.get("component_id")),
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

        # These attibutes are NOT available to sensor entity, if they do it should not be a select,enum or number entity
        for key in (
            "options",
            "list_items",
            "default_value",
            "unit_of_measure",
            "min_value",
            "max_value",
            "step_width",
        ):
            if (value := param.get(key)) is not None and value != []:
                attributes[key] = value

        if param.get("options"):
            attributes["raw_options"] = [
                option.get("label")
                for option in param.get("options", [])
            ]

        return redacted_parameter_attributes(attributes)

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
    def options(self) -> list[str] | None:
        """Return stable translation keys for enum options."""
        if not self.entity_description.is_enum:
            return None

        if self.entity_description.value_map is not None:
            return list(self.entity_description.slugified_options)

        param = self.data
        if param is None:
            return None
        return [slugify(item["label"]) for item in param.get("options", [])]

    @property
    def entity_registry_enabled_default(self) -> bool:
        enabled_value_state = self.entity_description.enabled_value_state
        if enabled_value_state is None:
            return super().entity_registry_enabled_default

        param = self.data
        if param is None:
            return False

        return param.get("value_state") == enabled_value_state

    @property
    def _raw_value(self) -> object | None:
        """Return the raw sensor value."""
        if self.entity_description.is_device_attribute:
            device = self._device

            if device is None:
                return None

            return getattr(device, self.parameter_key, None)

        param = self.data

        if param is None:
            return None

        return param.get("value")

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""

        value_fn = self.entity_description.value_fn
        if value_fn is not None:
            return value_fn(self)

        if self.parameter_key == "ventilation_percentage":
            return self._calculate_ventilation_percentage()

        if self.parameter_key in {
            "ip_address",
            "dns_server",
        }:
            if self.data is None:
                return None
            value = self.data.get("value")
            if not value:
                return None
            return str(value)

        _LOGGER.debug(
            "sensor value %s raw=%s",
            self.parameter_key,
            self._raw_value,
        )

        value = self._raw_value

        if value is None:
            return None

        if self.entity_description.is_enum:
            value_map = self.entity_description.value_map

            if value_map is not None:
                try:
                    mapped_slug = self.entity_description.slugified_value_map.get(int(value))
                except (TypeError, ValueError):
                    mapped_slug = None

                if mapped_slug is None:
                    _LOGGER.debug(
                        "Unknown enum value %s for %s",
                        value,
                        self.parameter_key,
                    )
                    return None

                _LOGGER.debug(
                    "Enum %s raw=%s mapped=%s options=%s",
                    self.parameter_key,
                    value,
                    mapped_slug,
                    self.options,
                )
                return mapped_slug

            param = self.data

            if param is not None:
                if (options_map := param.get("options_map")) is not None:
                    selected = options_map.get(str(value))
                else:
                    selected = next(
                        (
                            item["label"]
                            for item in param.get("options", [])
                            if item["value"] == str(value)
                        ),
                        None,
                    )

                if selected is not None:
                    return slugify(selected)

            return slugify(str(value))

        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)

        return int(number) if number.is_integer() else number

    @property
    def available(self) -> bool:
        """Return if entity is available."""

        device = self._device
        if device:
            parameters = device.parameters
        parameter_key = self.entity_description.parameter_key
        param = self.data

        if (
            param is None
            or param.get("value_state") == ValueState.INVALID
        ):
            _LOGGER.debug(
                "Brink sensor parameter unavailable: key=%s",
                parameter_key,
            )
            # return False

        if parameter_key == "ventilation_percentage":
            if device is None:
                return True

            parameters = device.parameters
            if not isinstance(parameters, dict):
                return False

            airflow_parameter = parameters.get("ventilation_mode_3_airflow")
            if not isinstance(airflow_parameter, dict):
                return False

            try:
                return float(airflow_parameter.get("max_value", 0)) > 0
            except (TypeError, ValueError):
                return False

        if parameter_key in {
            "cabinet_sound_power",
            "supply_sound_power",
            "exhaust_sound_power",
        }:
            return (
                self.coordinator.last_update_success
                and not self.has_blocking_error
                and device is not None
                and device.device_is_online
            )

        if parameter_key == "gateway_state":
            return self.coordinator.last_update_success

        if self.entity_description.is_device_attribute:
            return (
                self.coordinator.last_update_success
                and device is not None
                and getattr(device, parameter_key, None) is not None
            )

        return (
            super().available
            and param is not None
            and param.get("value_state") != ValueState.INVALID
        )

    def _calculate_cabinet_sound_power(self) -> float | None:
        """Calculate the estimated cabinet sound power."""
        airflow = self.cabinet_airflow
        pressure = self.cabinet_pressure

        if airflow is None or pressure is None:
            return None

        return estimate_sound_power(
            airflow=airflow,
            pressure=pressure,
            coefficients=CABINET_SOUND_POWER_COEFFICIENTS,
        )

    def _calculate_ventilation_percentage(self) -> int | None:
        """Calculate ventilation percentage based on configured airflow levels."""
        if self._device:
            parameters = self._device.parameters

        try:
            supply_flow = float(
                parameters["actual_supply_air_flow"]["value"]
            )
            exhaust_flow = float(
                parameters["actual_exhaust_air_flow"]["value"]
            )
            min_airflow = 0
            max_airflow = float(
                parameters["ventilation_mode_3_airflow"]["max_value"]
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            return None

        current_flow = (
            supply_flow
            + exhaust_flow
        ) / 2

        if max_airflow <= min_airflow:
            return None

        if current_flow <= min_airflow:
            return 0

        if current_flow >= max_airflow:
            return 100

        # Calculate percentage based on current flow
        fraction = (current_flow - min_airflow) / (max_airflow - min_airflow)
        return round(fraction * 100)

    @property
    def cabinet_airflow(self) -> float | None:
        """Return the average cabinet airflow in m³/h."""
        if self.supply_airflow is None or self.exhaust_airflow is None:
            return None

        return (self.supply_airflow + self.exhaust_airflow) / 2.0

    @property
    def cabinet_pressure(self) -> float | None:
        """Return the average cabinet pressure in Pa."""
        if self.supply_pressure is None or self.exhaust_pressure is None:
            return None

        return (self.supply_pressure + self.exhaust_pressure) / 2.0

    @property
    def cabinet_sound_power(self) -> float | None:
        """Return the estimated cabinet sound power."""
        airflow = self.cabinet_airflow
        pressure = self.cabinet_pressure

        if airflow is None or pressure is None:
            return None

        return estimate_sound_power(
            airflow=airflow,
            pressure=pressure,
            coefficients=CABINET_SOUND_POWER_COEFFICIENTS,
        )

    @property
    def supply_airflow(self) -> float | None:
        """Return the current supply airflow in m³/h."""
        return self._parameter_value(PARAM_SUPPLY_AIR_FLOW)

    @property
    def exhaust_airflow(self) -> float | None:
        """Return the current exhaust airflow in m³/h."""
        return self._parameter_value(PARAM_EXHAUST_AIR_FLOW)

    @property
    def supply_pressure(self) -> float | None:
        """Return the current supply channel pressure in Pa."""
        return self._parameter_value(PARAM_SUPPLY_AIR_PRESSURE)

    @property
    def exhaust_pressure(self) -> float | None:
        """Return the current exhaust channel pressure in Pa."""
        return self._parameter_value(PARAM_EXHAUST_AIR_PRESSURE)

    @property
    def supply_sound_power(self) -> float | None:
        """Return the estimated supply duct sound power."""
        airflow = self.supply_airflow
        pressure = self.supply_pressure

        if airflow is None or pressure is None:
            return None

        return estimate_sound_power(
            airflow=airflow,
            pressure=pressure,
            coefficients=SUPPLY_SOUND_POWER_COEFFICIENTS,
        )

    @property
    def exhaust_sound_power(self) -> float | None:
        """Return the estimated exhaust duct sound power."""
        airflow = self.exhaust_airflow
        pressure = self.exhaust_pressure

        if airflow is None or pressure is None:
            return None

        return estimate_sound_power(
            airflow=airflow,
            pressure=pressure,
            coefficients=EXHAUST_SOUND_POWER_COEFFICIENTS,
        )
