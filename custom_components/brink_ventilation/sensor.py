"""Support for Brink ventilation sensors."""
from __future__ import annotations

import logging
from typing import Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONCENTRATION_PARTS_PER_MILLION, UnitOfTemperature
from homeassistant.core import HomeAssistant

from custom_components.brink_ventilation import BrinkHomeDeviceEntity

from .const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Define sensor types with their properties
SENSOR_TYPES = {
    "co2": {
        "device_class": SensorDeviceClass.CO2,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": CONCENTRATION_PARTS_PER_MILLION,
        "icon": "mdi:molecule-co2",
        "patterns": ["PPM eBus CO2-sensor", "PPM CO2-sensor", "CO2-sensor"],
    },
    "temperature": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer",
        "patterns": ["temperatur", "Frischlufttemperatur", "Zulufttemperatur"],
    },
    "humidity": {
        "device_class": SensorDeviceClass.HUMIDITY,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": "%",
        "icon": "mdi:water-percent",
        "patterns": ["Feuchte", "humidity"],
    },
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the Brink Home sensor platform."""
    client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    entities = []

    _LOGGER.debug(f"Setting up Brink ventilation sensors")
    
    # Look for CO2 sensors and other specific sensors in the data
    for device_index, device_data in enumerate(coordinator.data):
        _LOGGER.debug(f"Device {device_index} available keys: {list(device_data.keys())}")
        
        # Check for CO2 sensors and other sensors that might be stored as top-level keys
        for key, value in device_data.items():
            if isinstance(value, dict) and "name" in value and "value" in value:
                # Check if the key matches any of our sensor patterns
                for sensor_type, properties in SENSOR_TYPES.items():
                    for pattern in properties["patterns"]:
                        if pattern.lower() in key.lower():
                            _LOGGER.debug(f"Found {sensor_type} sensor by key: {key}")
                            entities.append(
                                BrinkSensor(
                                    client,
                                    coordinator,
                                    device_index,
                                    key,
                                    value["name"],
                                    properties["device_class"],
                                    properties["state_class"],
                                    properties["unit"],
                                    properties["icon"]
                                )
                            )
            
                # Also check the name field in the value dict as before
                sensor_name = value.get("name", "")
                _LOGGER.debug(f"Checking potential sensor: {sensor_name}")
                
                for sensor_type, properties in SENSOR_TYPES.items():
                    for pattern in properties["patterns"]:
                        if pattern.lower() in sensor_name.lower():
                            _LOGGER.debug(f"Found {sensor_type} sensor by name: {sensor_name}")
                            entities.append(
                                BrinkSensor(
                                    client,
                                    coordinator,
                                    device_index,
                                    key,
                                    sensor_name,
                                    properties["device_class"],
                                    properties["state_class"],
                                    properties["unit"],
                                    properties["icon"]
                                )
                            )

    if entities:
        _LOGGER.info(f"Adding {len(entities)} sensor entities: {[e.entity_name for e in entities]}")
        async_add_entities(entities)
    else:
        _LOGGER.warning("No sensors found in the data. Make sure your Brink system has sensors and they are enabled.")


class BrinkSensor(BrinkHomeDeviceEntity, SensorEntity):
    """Representation of a Brink sensor."""

    def __init__(self, client, coordinator, device_index, entity_name, display_name, 
                 device_class, state_class, unit, icon):
        """Initialize the Brink sensor."""
        super().__init__(client, coordinator, device_index, entity_name)
        self._display_name = display_name
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon

    @property
    def id(self):
        """Return the ID of the sensor."""
        return f"{DOMAIN}_{self.entity_name}_{self.device_index}_sensor"

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return self.id

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.coordinator.data[self.device_index]['name']} {self._display_name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            # First try accessing the value directly as it might be a sensor key
            value = self.coordinator.data[self.device_index][self.entity_name]
            if isinstance(value, dict) and "value" in value:
                value = value["value"]
            
            # Attempt to convert to a number if possible
            try:
                if isinstance(value, str) and "." in value:
                    return float(value)
                elif isinstance(value, str):
                    return int(value)
                return value
            except (ValueError, TypeError):
                return value
        except (KeyError, TypeError, ValueError) as e:
            _LOGGER.debug(f"Error getting value for {self.entity_name}: {e}")
            return None