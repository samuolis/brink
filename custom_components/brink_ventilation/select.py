from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (
    BYPASS_OPERATION_LABELS,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    PARAM_BYPASS_OPERATION,
    PARAM_OPERATING_MODE,
)
from .entity import BrinkHomeDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the Brink select platform."""
    client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities = []
    for system_id, device in (coordinator.data or {}).items():
        parameters = device.get("parameters", {})
        if parameters.get(PARAM_OPERATING_MODE):
            entities.append(
                BrinkHomeModeSelectEntity(
                    client, coordinator, system_id, PARAM_OPERATING_MODE
                )
            )
        if parameters.get(PARAM_BYPASS_OPERATION):
            entities.append(
                BrinkHomeBypassOperationSelectEntity(
                    client, coordinator, system_id, PARAM_BYPASS_OPERATION
                )
            )

    async_add_entities(entities)


class BrinkHomeSelectEntity(BrinkHomeDeviceEntity, SelectEntity):
    """Base Brink select entity."""

    async def _async_write_value(self, value: str) -> None:
        param = self.data
        if param is None or param.get("value_id") is None:
            raise HomeAssistantError(f"{self.parameter_name} parameter is unavailable")

        await self.client.write_parameters(
            self.system_id,
            [(int(param["value_id"]), value)],
        )
        param["value"] = value
        self.coordinator.async_set_updated_data(dict(self.coordinator.data))
        await self.coordinator.async_request_refresh()

    @property
    def name(self):
        return f"{self.device_name} {self.parameter_name}"

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.system_id}_{self.parameter_key}_select"

    @property
    def icon(self):
        return "mdi:hvac"


class BrinkHomeModeSelectEntity(BrinkHomeSelectEntity):
    """Representation of the Brink operating mode selector."""

    async def async_select_option(self, option: str) -> None:
        param = self.data
        if param is None:
            raise HomeAssistantError("Operating mode parameter is unavailable")

        selected = next(
            (item for item in param.get("options", []) if item["label"] == option),
            None,
        )
        if selected is None:
            raise HomeAssistantError(f"Unknown operating mode option: {option}")

        await self._async_write_value(selected["value"])

    @property
    def current_option(self) -> str | None:
        param = self.data
        if param is None:
            return None
        for option in param.get("options", []):
            if option["value"] == str(param.get("value")):
                return option["label"]
        return None

    @property
    def options(self) -> list[str]:
        param = self.data
        if param is None:
            return []
        return [item["label"] for item in param.get("options", [])]


class BrinkHomeBypassOperationSelectEntity(BrinkHomeSelectEntity):
    """Representation of the Brink bypass operation selector."""

    @property
    def name(self):
        return f"{self.device_name} Bypass Operation"

    async def async_select_option(self, option: str) -> None:
        selected_value = next(
            (
                value
                for value, label in BYPASS_OPERATION_LABELS.items()
                if label == option
            ),
            None,
        )
        if selected_value is None:
            raise HomeAssistantError(f"Unknown bypass operation option: {option}")

        await self._async_write_value(selected_value)

    @property
    def current_option(self) -> str | None:
        param = self.data
        if param is None:
            return None
        return BYPASS_OPERATION_LABELS.get(str(param.get("value")))

    @property
    def options(self) -> list[str]:
        return list(BYPASS_OPERATION_LABELS.values())
