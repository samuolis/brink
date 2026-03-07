from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant

from .const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    PARAM_BYPASS_VALVE_STATUS,
    PARAM_CO2_SENSOR_1,
    PARAM_CO2_SENSOR_2,
    PARAM_CO2_SENSOR_3,
    PARAM_CO2_SENSOR_4,
    PARAM_DAYS_SINCE_FILTER_RESET,
    PARAM_EXHAUST_AIR_FLOW,
    PARAM_EXHAUST_TEMP,
    PARAM_FRESH_AIR_TEMP,
    PARAM_HUMIDITY,
    PARAM_PREHEATER_STATUS,
    PARAM_REMAINING_DURATION,
    PARAM_SUPPLY_AIR_FLOW,
)
from .entity import BrinkHomeDeviceEntity


@dataclass(frozen=True)
class BrinkSensorDescription(SensorEntityDescription):
    """Describe a Brink sensor entity."""

    parameter_key: str = ""
    is_enum: bool = False
    required_value_state: int | None = None


SENSOR_DESCRIPTIONS: tuple[BrinkSensorDescription, ...] = (
    BrinkSensorDescription(
        key=PARAM_SUPPLY_AIR_FLOW,
        name="Supply Air Flow",
        parameter_key=PARAM_SUPPLY_AIR_FLOW,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key=PARAM_EXHAUST_AIR_FLOW,
        name="Exhaust Air Flow",
        parameter_key=PARAM_EXHAUST_AIR_FLOW,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key=PARAM_FRESH_AIR_TEMP,
        name="Fresh Air Temperature",
        parameter_key=PARAM_FRESH_AIR_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key=PARAM_EXHAUST_TEMP,
        name="Exhaust Air Temperature",
        parameter_key=PARAM_EXHAUST_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key=PARAM_HUMIDITY,
        name="Humidity",
        parameter_key=PARAM_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        required_value_state=1,
    ),
    BrinkSensorDescription(
        key=PARAM_DAYS_SINCE_FILTER_RESET,
        name="Days Since Filter Reset",
        parameter_key=PARAM_DAYS_SINCE_FILTER_RESET,
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key=PARAM_REMAINING_DURATION,
        name="Remaining Mode Duration",
        parameter_key=PARAM_REMAINING_DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key=PARAM_PREHEATER_STATUS,
        name="Preheater Status",
        parameter_key=PARAM_PREHEATER_STATUS,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_enum=True,
        required_value_state=1,
    ),
    BrinkSensorDescription(
        key=PARAM_BYPASS_VALVE_STATUS,
        name="Bypass Valve Status",
        parameter_key=PARAM_BYPASS_VALVE_STATUS,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_enum=True,
    ),
    BrinkSensorDescription(
        key=PARAM_CO2_SENSOR_1,
        name="CO2 Sensor 1",
        parameter_key=PARAM_CO2_SENSOR_1,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        required_value_state=1,
    ),
    BrinkSensorDescription(
        key=PARAM_CO2_SENSOR_2,
        name="CO2 Sensor 2",
        parameter_key=PARAM_CO2_SENSOR_2,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        required_value_state=1,
    ),
    BrinkSensorDescription(
        key=PARAM_CO2_SENSOR_3,
        name="CO2 Sensor 3",
        parameter_key=PARAM_CO2_SENSOR_3,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        required_value_state=1,
    ),
    BrinkSensorDescription(
        key=PARAM_CO2_SENSOR_4,
        name="CO2 Sensor 4",
        parameter_key=PARAM_CO2_SENSOR_4,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        required_value_state=1,
    ),
)


def _should_create_sensor(device: dict, description: BrinkSensorDescription) -> bool:
    """Return True when the Brink parameter should be exposed as a sensor."""
    param = device.get("parameters", {}).get(description.parameter_key)
    if not param:
        return False

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

    entities = [
        BrinkHomeSensorEntity(client, coordinator, system_id, description)
        for system_id, device in (coordinator.data or {}).items()
        for description in SENSOR_DESCRIPTIONS
        if _should_create_sensor(device, description)
    ]
    async_add_entities(entities)


class BrinkHomeSensorEntity(BrinkHomeDeviceEntity, SensorEntity):
    """Representation of a Brink sensor."""

    entity_description: BrinkSensorDescription

    def __init__(self, client, coordinator, system_id: int, description: BrinkSensorDescription):
        """Initialize the Brink sensor."""
        super().__init__(client, coordinator, system_id, description.parameter_key)
        self.entity_description = description

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.system_id}_{self.parameter_key}_sensor"

    @property
    def name(self):
        label = self.entity_description.name or self.parameter_name
        return f"{self.device_name} {label}"

    @property
    def options(self) -> list[str] | None:
        if not self.entity_description.is_enum:
            return None

        param = self.data
        if param is None:
            return None
        return [item["label"] for item in param.get("options", [])]

    @property
    def native_value(self):
        param = self.data
        if param is None:
            return None

        value = param.get("value")
        if value is None:
            return None

        if self.entity_description.is_enum:
            selected = next(
                (item["label"] for item in param.get("options", []) if item["value"] == str(value)),
                None,
            )
            return selected or str(value)

        try:
            number = float(value)
        except (TypeError, ValueError):
            return value

        if number.is_integer():
            return int(number)
        return number
