from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    GATEWAY_STATE_LABELS,
    GATEWAY_STATE_ONLINE,
    PARAM_FILTER_STATUS,
)
from .entity import BrinkHomeDeviceEntity, BrinkHomeSystemEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the Brink filter status binary sensor platform."""
    client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities = []
    for system_id, device in (coordinator.data or {}).items():
        if device.get("gateway_state") is not None:
            entities.append(BrinkSystemOnlineBinarySensor(client, coordinator, system_id))
        if device.get("parameters", {}).get(PARAM_FILTER_STATUS):
            entities.append(
                BrinkFilterNeedChangeBinarySensor(
                    client, coordinator, system_id, PARAM_FILTER_STATUS
                )
            )

    async_add_entities(entities)


def _gateway_state_value(device: dict | None) -> int | None:
    """Normalize the Brink gateway state."""
    if device is None:
        return None

    state = device.get("gateway_state")
    try:
        return int(state)
    except (TypeError, ValueError):
        return None


class BrinkSystemOnlineBinarySensor(BrinkHomeSystemEntity, BinarySensorEntity):
    """Binary sensor that reflects whether the Brink system is online."""

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.system_id}_online"

    @property
    def name(self):
        return f"{self.device_name} Online"

    @property
    def is_on(self):
        state = _gateway_state_value(self._device)
        if state is None:
            return None
        return state == GATEWAY_STATE_ONLINE

    @property
    def device_class(self):
        return BinarySensorDeviceClass.CONNECTIVITY

    @property
    def extra_state_attributes(self):
        state = _gateway_state_value(self._device)
        if state is None:
            return None

        return {
            "gateway_state": state,
            "gateway_state_label": GATEWAY_STATE_LABELS.get(state, "unknown"),
        }


class BrinkFilterNeedChangeBinarySensor(BrinkHomeDeviceEntity, BinarySensorEntity):
    """Binary sensor that indicates when the Brink filter needs attention."""

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.system_id}_{self.parameter_key}_binary_sensor"

    @property
    def name(self):
        return f"{self.device_name} {self.parameter_name}"

    @property
    def icon(self):
        return "mdi:air-filter"

    @property
    def is_on(self):
        param = self.data
        if param is None:
            return None
        return str(param.get("value")) == "1"

    @property
    def device_class(self):
        return BinarySensorDeviceClass.PROBLEM
