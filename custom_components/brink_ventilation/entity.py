"""Base entity support for Brink ventilation."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_MODEL, DEFAULT_NAME, DOMAIN


class BrinkHomeSystemEntity(CoordinatorEntity):
    """Common entity helpers for a Brink system."""

    def __init__(self, client, coordinator, system_id: int) -> None:
        """Initialize the Brink system entity."""
        super().__init__(coordinator)
        self.client = client
        self.system_id = system_id

    @property
    def _device(self) -> dict[str, Any] | None:
        """Return the current device payload."""
        data = self.coordinator.data or {}
        return data.get(self.system_id)

    @property
    def device_name(self) -> str:
        """Return the Brink system display name."""
        device = self._device
        if device is None:
            return DEFAULT_NAME
        return device.get("name", DEFAULT_NAME)

    @property
    def device_info(self):
        """Return device info for the Brink entity."""
        device = self._device or {}
        return {
            "identifiers": {(DOMAIN, str(self.system_id))},
            "name": self.device_name,
            "manufacturer": DEFAULT_NAME,
            "model": device.get("model", DEFAULT_MODEL),
            "serial_number": device.get("serial_number"),
            "sw_version": device.get("sw_version"),
        }

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.coordinator.last_update_success and self._device is not None


class BrinkHomeDeviceEntity(BrinkHomeSystemEntity):
    """Common entity helpers for a Brink system parameter."""

    def __init__(self, client, coordinator, system_id: int, parameter_key: str) -> None:
        """Initialize the Brink parameter entity."""
        super().__init__(client, coordinator, system_id)
        self.parameter_key = parameter_key

    @property
    def data(self) -> dict[str, Any] | None:
        """Return the current parameter payload."""
        device = self._device
        if device is None:
            return None
        return device.get("parameters", {}).get(self.parameter_key)

    @property
    def parameter_name(self) -> str:
        """Return the translated parameter name."""
        param = self.data
        if param is None:
            return self.parameter_key.replace("_", " ")
        return param.get("name", self.parameter_key.replace("_", " "))

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return super().available and self.data is not None
