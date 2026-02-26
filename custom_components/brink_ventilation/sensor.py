"""Sensor entities for Brink Home Ventilation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BrinkConfigEntry
from .const import (
    ACTIVE_CONTROL_STATUS_MAP,
    BYPASS_VALVE_STATUS_MAP,
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
    PARAM_VENTILATION_LEVEL,
    PREHEATER_STATUS_MAP,
    SEASON_SUMMER,
    SEASON_WINTER,
)
from .coordinator import BrinkDataCoordinator
from .entity import BrinkHomeDeviceEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


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
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BrinkSensorDescription(
        key="exhaust_air_flow",
        translation_key="exhaust_air_flow",
        param_id=PARAM_EXHAUST_AIR_FLOW,
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
        entity_registry_enabled_default=False,
    ),
    BrinkSensorDescription(
        key="days_since_filter_reset",
        translation_key="days_since_filter_reset",
        param_id=PARAM_DAYS_SINCE_FILTER_RESET,
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="remaining_duration",
        translation_key="remaining_duration",
        param_id=PARAM_REMAINING_DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BrinkSensorDescription(
        key="active_control_status",
        translation_key="active_control_status",
        param_id=PARAM_ACTIVE_CONTROL_STATUS,
        device_class=SensorDeviceClass.ENUM,
        options=list(ACTIVE_CONTROL_STATUS_MAP.values()),
        enum_map=ACTIVE_CONTROL_STATUS_MAP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BrinkSensorDescription(
        key="bypass_valve_status",
        translation_key="bypass_valve_status",
        param_id=PARAM_BYPASS_VALVE_STATUS,
        device_class=SensorDeviceClass.ENUM,
        options=list(BYPASS_VALVE_STATUS_MAP.values()),
        enum_map=BYPASS_VALVE_STATUS_MAP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="preheater_status",
        translation_key="preheater_status",
        param_id=PARAM_PREHEATER_STATUS,
        device_class=SensorDeviceClass.ENUM,
        options=list(PREHEATER_STATUS_MAP.values()),
        enum_map=PREHEATER_STATUS_MAP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkSensorDescription(
        key="co2_sensor_1",
        translation_key="co2_sensor_1",
        param_id=PARAM_CO2_SENSOR_1,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    BrinkSensorDescription(
        key="co2_sensor_2",
        translation_key="co2_sensor_2",
        param_id=PARAM_CO2_SENSOR_2,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    BrinkSensorDescription(
        key="co2_sensor_3",
        translation_key="co2_sensor_3",
        param_id=PARAM_CO2_SENSOR_3,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    BrinkSensorDescription(
        key="co2_sensor_4",
        translation_key="co2_sensor_4",
        param_id=PARAM_CO2_SENSOR_4,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BrinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Brink Home sensor platform."""
    coordinator = entry.runtime_data.coordinator
    known_systems: set[int] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Detect new devices and add sensor entities for them."""
        if not coordinator.data:
            return

        new_systems = set(coordinator.data) - known_systems
        if not new_systems:
            return

        known_systems.update(new_systems)
        entities: list[SensorEntity] = []

        for system_id in new_systems:
            device = coordinator.data[system_id]
            found_params: set[int] = set()
            for component in device.get("components", []):
                params = component.get("parameters", {})
                for desc in SENSOR_DESCRIPTIONS:
                    if desc.param_id in params and desc.param_id not in found_params:
                        entities.append(
                            BrinkHomeSensorEntity(
                                coordinator=coordinator,
                                system_id=system_id,
                                param_id=desc.param_id,
                                entity_key=desc.key,
                                description=desc,
                            )
                        )
                        found_params.add(desc.param_id)

        # Add automation-controller-based sensors (not tied to API parameters)
        for system_id in new_systems:
            entities.append(
                BrinkExtraVentRemainingEntity(coordinator, system_id)
            )
            entities.append(
                BrinkCurrentSeasonEntity(coordinator, system_id)
            )
            entities.append(BrinkHumidityDeltaEntity(coordinator, system_id))

        if entities:
            _LOGGER.debug("Adding %s sensor entities", len(entities))
            async_add_entities(entities)

    _async_add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class BrinkHomeSensorEntity(BrinkHomeDeviceEntity, SensorEntity):
    """Representation of a Brink sensor."""

    def __init__(
        self,
        coordinator: BrinkDataCoordinator,
        system_id: int,
        param_id: int,
        entity_key: str,
        description: BrinkSensorDescription,
    ) -> None:
        """Initialize the Brink sensor."""
        super().__init__(coordinator, system_id, param_id, entity_key)
        self.entity_description = description
        self._enum_map = description.enum_map

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{DOMAIN}_{self._system_id}_{self.entity_description.key}"

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


class BrinkExtraVentRemainingEntity(BrinkHomeDeviceEntity, SensorEntity):
    """Sensor for extra ventilation time remaining (from automation controller)."""

    _attr_translation_key = "extra_ventilation_remaining"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: BrinkDataCoordinator,
        system_id: int,
    ) -> None:
        """Initialize the extra ventilation remaining sensor."""
        super().__init__(
            coordinator,
            system_id,
            PARAM_VENTILATION_LEVEL,
            "extra_ventilation_remaining",
        )

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{DOMAIN}_{self._system_id}_extra_ventilation_remaining"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self._device is not None

    @property
    def native_value(self) -> int | None:
        """Return the extra ventilation time remaining in minutes."""
        return self.coordinator.automation_controller.boost_remaining_minutes


class BrinkCurrentSeasonEntity(BrinkHomeDeviceEntity, SensorEntity):
    """Sensor for the current season (from automation controller)."""

    _attr_translation_key = "current_season"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [SEASON_SUMMER, SEASON_WINTER]
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: BrinkDataCoordinator,
        system_id: int,
    ) -> None:
        """Initialize the current season sensor."""
        super().__init__(
            coordinator,
            system_id,
            PARAM_VENTILATION_LEVEL,
            "current_season",
        )

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{DOMAIN}_{self._system_id}_current_season"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self._device is not None

    @property
    def native_value(self) -> str | None:
        """Return the current season."""
        return self.coordinator.automation_controller.season


class BrinkHumidityDeltaEntity(BrinkHomeDeviceEntity, SensorEntity):
    """Sensor showing the maximum humidity change across monitored sensors."""

    _attr_translation_key = "humidity_delta"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: BrinkDataCoordinator,
        system_id: int,
    ) -> None:
        """Initialize the humidity delta sensor."""
        super().__init__(coordinator, system_id, PARAM_VENTILATION_LEVEL, "humidity_delta")

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{DOMAIN}_{self._system_id}_humidity_delta"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self._device is not None

    @property
    def native_value(self) -> float:
        """Return the maximum humidity delta across all monitored sensors."""
        return self.coordinator.automation_controller.max_humidity_delta
