from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN, PARAM_OPERATING_MODE
from .entity import BrinkHomeDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the Brink operating mode select platform."""
    client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities = [
        BrinkHomeModeSelectEntity(client, coordinator, system_id, PARAM_OPERATING_MODE)
        for system_id, device in (coordinator.data or {}).items()
        if device.get("parameters", {}).get(PARAM_OPERATING_MODE)
    ]
    async_add_entities(entities)


class BrinkHomeModeSelectEntity(BrinkHomeDeviceEntity, SelectEntity):
    """Representation of the Brink operating mode selector."""

    async def async_select_option(self, option: str):
        param = self.data
        if param is None or param.get("value_id") is None:
            raise HomeAssistantError("Operating mode parameter is unavailable")

        selected = next(
            (item for item in param.get("options", []) if item["label"] == option),
            None,
        )
        if selected is None:
            raise HomeAssistantError(f"Unknown operating mode option: {option}")

        await self.client.write_parameters(
            self.system_id,
            [(int(param["value_id"]), selected["value"])],
        )
        param["value"] = selected["value"]
        self.coordinator.async_set_updated_data(dict(self.coordinator.data))
        await self.coordinator.async_request_refresh()

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

    @property
    def name(self):
        return f"{self.device_name} {self.parameter_name}"

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.system_id}_{self.parameter_key}_select"

    @property
    def icon(self):
        return "mdi:hvac"
