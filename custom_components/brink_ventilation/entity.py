"""Base entity for Brink Home ventilation."""

from __future__ import annotations

from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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
        param_id: str,
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
    def _parameters(self) -> dict[str, dict[str, Any]]:
        """Return the parameter dict for this entity's component."""
        component = self._component
        return component.get("parameters", {}) if component else {}

    @property
    def _param(self) -> dict[str, Any] | None:
        """Return this entity's specific parameter dict."""
        return self._parameters.get(self._param_id)

    def _get_param_any_component(self, param_id: str) -> dict[str, Any] | None:
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


def setup_dynamic_platform(
    coordinator: BrinkDataCoordinator,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    entity_factory: Callable[[BrinkDataCoordinator, set[int]], list],
) -> None:
    """Set up dynamic entity discovery for a platform.

    entity_factory is called with (coordinator, new_system_ids: set[int])
    and must return a list of entities to add.
    """
    known_systems: set[int] = set()

    @callback
    def _async_add_new_devices() -> None:
        if not coordinator.data:
            return
        new_systems = set(coordinator.data) - known_systems
        if not new_systems:
            return
        known_systems.update(new_systems)
        entities = entity_factory(coordinator, new_systems)
        if entities:
            async_add_entities(entities)

    _async_add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))
