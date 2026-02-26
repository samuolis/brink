"""Base entity for Brink Home ventilation."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_MODEL, DOMAIN, MANUFACTURER, PARAM_SOFTWARE_LABEL
from .coordinator import BrinkDataCoordinator


class BrinkHomeDeviceEntity(CoordinatorEntity[BrinkDataCoordinator]):
    """Defines a base Brink home device entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BrinkDataCoordinator,
        system_id: int,
        param_id: int,
        entity_key: str,
    ) -> None:
        """Initialize the Brink home entity."""
        super().__init__(coordinator)
        self._system_id = system_id
        self._param_id = param_id
        self._entity_key = entity_key

    @property
    def _device(self) -> dict[str, Any] | None:
        """Return the device dict for this entity's system."""
        data = self.coordinator.data
        if data is None:
            return None
        return data.get(self._system_id)

    @property
    def _component(self) -> dict[str, Any] | None:
        """Return the component containing this entity's parameter."""
        device = self._device
        if device is None:
            return None
        for component in device.get("components", []):
            if self._param_id in component.get("parameters", {}):
                return component
        return None

    @property
    def _parameters(self) -> dict[int, dict[str, Any]]:
        """Return the parameter dict for this entity's component."""
        component = self._component
        return component.get("parameters", {}) if component else {}

    @property
    def _param(self) -> dict[str, Any] | None:
        """Return this entity's specific parameter dict."""
        return self._parameters.get(self._param_id)

    def _get_param_any_component(self, param_id: int) -> dict[str, Any] | None:
        """Search all components for a parameter by ID."""
        device = self._device
        if device is None:
            return None
        for component in device.get("components", []):
            param = component.get("parameters", {}).get(param_id)
            if param is not None:
                return param
        return None

    @property
    def _gateway_id(self) -> int | None:
        """Return the gateway ID for this entity's device."""
        device = self._device
        return device.get("gateway_id") if device else None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info for the Brink entity."""
        device = self._device
        if device is None:
            return None

        component = self._component
        model = component.get("name", DEFAULT_MODEL) if component else DEFAULT_MODEL

        sw_param = self._parameters.get(PARAM_SOFTWARE_LABEL)
        sw_version: str | None = sw_param.get("value") if sw_param else None

        return DeviceInfo(
            identifiers={(DOMAIN, str(self._system_id))},
            name=device.get("name", "Brink Ventilation"),
            manufacturer=MANUFACTURER,
            model=model,
            serial_number=device.get("serial_number"),
            sw_version=sw_version,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self._device is not None
            and self._param is not None
        )
