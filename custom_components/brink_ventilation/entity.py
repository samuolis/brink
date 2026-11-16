"""Base entity support for Brink ventilation."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DOMAIN,
    PARAM_EXHAUST_AIR_FLOW,
    PARAM_EXHAUST_AIR_PRESSURE,
    PARAM_SUPPLY_AIR_FLOW,
    PARAM_SUPPLY_AIR_PRESSURE,
)
from .coordinator import BrinkCoordinator
from .models import BrinkDeviceData
from .sound import CABINET_SOUND_POWER_COEFFICIENTS, estimate_sound_power


# class BrinkHomeSystemEntity(CoordinatorEntity):
class BrinkHomeSystemEntity(CoordinatorEntity[BrinkCoordinator]):
    """Common entity helpers for a Brink system."""

    def __init__(self, client, coordinator, system_id: int) -> None:
        """Initialize the Brink system entity."""
        super().__init__(coordinator)
        self.client = client
        self.system_id = system_id

    @property
    def _device(self) -> BrinkDeviceData | None:
        """Return the current device."""
        if self.coordinator.data is None:
            return None

        return self.coordinator.data.get(self.system_id)

    @property
    def device_name(self) -> str:
        """Return the Brink system display name."""
        device = self._device

        return DEFAULT_NAME if device is None else device.name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the Brink entity."""
        device = self._device
        name = self.device_name
        if device is None:
            return DeviceInfo(
                identifiers={(DOMAIN, str(self.system_id))},
                name=self.device_name,
                manufacturer=DEFAULT_NAME,
                model=DEFAULT_MODEL,
            )
        kwargs: dict[str, object] = (
            {"configuration_url": "http://brink.local/"}
            if device.ip_address
            else {}
        )
        return DeviceInfo(
            identifiers={(DOMAIN, str(self.system_id))},
            name=device.model or self.device_name,
            manufacturer=DEFAULT_NAME,
            model=device.model or DEFAULT_MODEL,
            serial_number=device.serial_number,
            sw_version=device.sw_version,
            **kwargs,
        )

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return (
            super().available
            and self._device is not None
        )


class BrinkGatewayStateSensor(BrinkHomeSystemEntity):
    """Sensor for the gateway state."""

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return super().available


class BrinkHomeDeviceEntity(BrinkHomeSystemEntity):
    """Common entity helpers for a Brink system parameter."""

    # coordinator: BrinkCoordinator

    def __init__(self, client, coordinator: BrinkCoordinator, system_id: int, parameter_key: str) -> None:
        """Initialize the Brink parameter entity."""
        super().__init__(client, coordinator, system_id)
        # self.client = client
        # self.system_id = system_id
        self.parameter_key = parameter_key

    @property
    def data(self) -> dict[str, object] | None:
        """Return the current parameter payload."""
        parameter = self._parameters.get(self.parameter_key)

        return parameter if isinstance(parameter, dict) else None

    @property
    def _parameters(self) -> dict[str, dict[str, object]]:
        """Return the device parameters."""
        device = self._device

        return {} if device is None else device.parameters

    @property
    def parameter_name(self) -> str:
        """Return the translated parameter name."""
        param = self.data

        default_name = self.parameter_key.replace("_", " ")

        if param is None:
            return default_name

        name = param.get("name")

        return str(name) if name is not None else default_name

    @property
    def parameter_value(self) -> str | None:
        """Return the current parameter value."""
        data = self.data

        if data is None:
            return None

        value = data.get("value")

        return None if value is None else str(value)

    @property
    def has_blocking_error(self) -> bool:
        """Return True if the device has a blocking fault."""
        device = self._device
        return device.has_blocking_error if device is not None else False

    @property
    def api_is_online(self) -> bool:
        """Return whether the Brink API is online."""
        return self.coordinator.api_is_online

    @property
    def api_error(self) -> str | None:
        """Return the last Brink API error."""
        return self.coordinator.api_error

    @property
    def api_error_code(self) -> int | None:
        """Return the last Brink API error code."""
        return self.coordinator.api_error_code

    @property
    def api_error_type(self) -> str | None:
        """Return the last Brink API error type."""
        return self.coordinator.api_error_type

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        device = self._device

        if not self.coordinator.last_update_success:
            return False

        if self.has_blocking_error:
            return False

        return (
            super().available
            and self.data is not None
            and device is not None
            and device.device_is_online
        )

    @property
    def cabinet_sound_power(self) -> float | None:
        """Return the estimated cabinet sound power."""
        parameters = self._parameters

        supply_airflow = parameters.get(PARAM_SUPPLY_AIR_FLOW)
        exhaust_airflow = parameters.get(PARAM_EXHAUST_AIR_FLOW)
        supply_pressure = parameters.get(PARAM_SUPPLY_AIR_PRESSURE)
        exhaust_pressure = parameters.get(PARAM_EXHAUST_AIR_PRESSURE)

        if not all(
            isinstance(parameter, dict)
            for parameter in (
                supply_airflow,
                exhaust_airflow,
                supply_pressure,
                exhaust_pressure,
            )
        ):
            return None

        try:
            airflow = (
                float(supply_airflow["value"])
                + float(exhaust_airflow["value"])
            ) / 2.0

            pressure = (
                float(supply_pressure["value"])
                + float(exhaust_pressure["value"])
            ) / 2.0
        except (KeyError, TypeError, ValueError):
            return None

        return estimate_sound_power(
            airflow=airflow,
            pressure=pressure,
            coefficients=CABINET_SOUND_POWER_COEFFICIENTS,
        )

    def _parameter_value(
        self,
        parameter_key: str,
    ) -> float | None:
        """Return the numeric value of a parameter."""
        parameter = self._parameters.get(parameter_key)

        if not isinstance(parameter, dict):
            return None

        value = parameter.get("value")

        try:
            return float(value)
        except (TypeError, ValueError):
            return None


