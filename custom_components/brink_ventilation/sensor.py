"""Sensor entities for Brink Home Ventilation."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    CONCENTRATION_PARTS_PER_MILLION,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BrinkHomeDeviceEntity
from .const import (
    ACTIVE_CONTROL_STATUS_MAP,
    BYPASS_VALVE_STATUS_MAP,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    PARAM_ACTIVE_CONTROL_STATUS,
    PARAM_BYPASS_VALVE_STATUS,
    PARAM_CO2_SENSOR_1,
    PARAM_CO2_SENSOR_2,
    PARAM_CO2_SENSOR_3,
    PARAM_CO2_SENSOR_4,
    PARAM_DAYS_SINCE_FILTER_RESET,
    PARAM_EXHAUST_AIR_FLOW,
    PARAM_FRESH_AIR_TEMP,
    PARAM_HUMIDITY,
    PARAM_PREHEATER_STATUS,
    PARAM_REMAINING_DURATION,
    PARAM_SUPPLY_AIR_FLOW,
    PARAM_SUPPLY_TEMP,
    PREHEATER_STATUS_MAP,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BrinkSensorDescription(SensorEntityDescription):
    """Describes a Brink sensor entity."""

    param_id: int = 0
    enum_map: dict[str, str] | None = None


SENSOR_DESCRIPTIONS: list[BrinkSensorDescription] = [
    BrinkSensorDescription(
        key="supply_air_flow",
        translation_key="supply_air_flow",
        param_id=PARAM_SUPPLY_AIR_FLOW,
        icon="mdi:fan",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key="exhaust_air_flow",
        translation_key="exhaust_air_flow",
        param_id=PARAM_EXHAUST_AIR_FLOW,
        icon="mdi:fan",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key="fresh_air_temp",
        translation_key="fresh_air_temp",
        param_id=PARAM_FRESH_AIR_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key="supply_temp",
        translation_key="supply_temp",
        param_id=PARAM_SUPPLY_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key="humidity",
        translation_key="humidity",
        param_id=PARAM_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key="days_since_filter_reset",
        translation_key="days_since_filter_reset",
        param_id=PARAM_DAYS_SINCE_FILTER_RESET,
        icon="mdi:air-filter",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key="remaining_duration",
        translation_key="remaining_duration",
        param_id=PARAM_REMAINING_DURATION,
        icon="mdi:timer",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key="active_control_status",
        translation_key="active_control_status",
        param_id=PARAM_ACTIVE_CONTROL_STATUS,
        icon="mdi:information",
        device_class=SensorDeviceClass.ENUM,
        options=list(ACTIVE_CONTROL_STATUS_MAP.values()),
        enum_map=ACTIVE_CONTROL_STATUS_MAP,
    ),
    BrinkSensorDescription(
        key="bypass_valve_status",
        translation_key="bypass_valve_status",
        param_id=PARAM_BYPASS_VALVE_STATUS,
        icon="mdi:valve",
        device_class=SensorDeviceClass.ENUM,
        options=list(BYPASS_VALVE_STATUS_MAP.values()),
        enum_map=BYPASS_VALVE_STATUS_MAP,
    ),
    BrinkSensorDescription(
        key="preheater_status",
        translation_key="preheater_status",
        param_id=PARAM_PREHEATER_STATUS,
        icon="mdi:radiator",
        device_class=SensorDeviceClass.ENUM,
        options=list(PREHEATER_STATUS_MAP.values()),
        enum_map=PREHEATER_STATUS_MAP,
    ),
    BrinkSensorDescription(
        key="co2_sensor_1",
        translation_key="co2_sensor_1",
        param_id=PARAM_CO2_SENSOR_1,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key="co2_sensor_2",
        translation_key="co2_sensor_2",
        param_id=PARAM_CO2_SENSOR_2,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key="co2_sensor_3",
        translation_key="co2_sensor_3",
        param_id=PARAM_CO2_SENSOR_3,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key="co2_sensor_4",
        translation_key="co2_sensor_4",
        param_id=PARAM_CO2_SENSOR_4,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Brink Home sensor platform."""
    client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities = []
    for device_index, device in enumerate(coordinator.data):
        found_params = set()
        for component in device.get("components", []):
            params = component.get("parameters", {})
            for desc in SENSOR_DESCRIPTIONS:
                if desc.param_id in params and desc.param_id not in found_params:
                    entities.append(
                        BrinkHomeSensorEntity(
                            client=client,
                            coordinator=coordinator,
                            device_index=device_index,
                            param_id=desc.param_id,
                            entity_key=desc.key,
                            description=desc,
                        )
                    )
                    found_params.add(desc.param_id)

    _LOGGER.debug("Setting up %s sensor entities", len(entities))
    async_add_entities(entities)


class BrinkHomeSensorEntity(BrinkHomeDeviceEntity, SensorEntity):
    """Representation of a Brink sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        client,
        coordinator,
        device_index: int,
        param_id: int,
        entity_key: str,
        description: BrinkSensorDescription,
    ):
        """Initialize the Brink sensor."""
        super().__init__(client, coordinator, device_index, param_id, entity_key)
        self.entity_description = description
        self._enum_map = description.enum_map

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{DOMAIN}_{self.system_id}_{self.entity_description.key}"

    @property
    def native_value(self) -> str | float | None:
        """Return the sensor value."""
        param = self._param
        if param is None:
            return None
        value = param.get("value")
        if value is None:
            return None

        if self._enum_map is not None:
            return self._enum_map.get(str(value), str(value))

        try:
            return float(value)
        except (ValueError, TypeError):
            return value
