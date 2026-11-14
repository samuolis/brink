"""Regression tests for Brink 2.0 entity identity, privacy and safe writes."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.brink_ventilation.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    BrinkHomeBinarySensorEntity,
)
from custom_components.brink_ventilation.const import DOMAIN, PARAM_FILTER_STATUS
from custom_components.brink_ventilation.core.parameter_validation import (
    finite_parameter_bounds,
    is_parameter_writable,
    writable_value_id,
)
from custom_components.brink_ventilation.models import BrinkDeviceData
from custom_components.brink_ventilation.number import (
    BrinkHomeNumberEntity,
    BrinkNumberEntityDescription,
)
from custom_components.brink_ventilation.select import (
    BrinkHomeSelectEntity,
    BrinkSelectEntityDescription,
)
from custom_components.brink_ventilation.sensor import (
    BrinkSensorDescription,
    _should_create_sensor,
    async_setup_entry,
)


def _dependencies(
    parameters: dict[str, dict[str, object]] | None = None,
    *,
    gateway_state: str | None = "2",
) -> tuple[MagicMock, MagicMock, BrinkDeviceData]:
    """Build one Brink unit with synthetic metadata and no live transport."""
    device = BrinkDeviceData(
        api_is_online=True,
        system_id=101,
        name="Synthetic unit",
        internal_name="Synthetic unit",
        model="Flair",
        serial_number=None,
        gateway_state=gateway_state,
        gateway_type_id=3,
        device_is_online=True,
        ip_address=None,
        dns_server=None,
        sw_version=None,
        alerts=[],
        parameters=parameters or {},
    )
    client = MagicMock(write_parameters=AsyncMock())
    coordinator = MagicMock(data={101: device}, last_update_success=True)
    coordinator.async_request_refresh = AsyncMock()
    return client, coordinator, device


def _binary_sensor(
    key: str, client: MagicMock, coordinator: MagicMock
) -> BrinkHomeBinarySensorEntity:
    """Instantiate one actual binary-sensor description by semantic key."""
    description = next(item for item in BINARY_SENSOR_DESCRIPTIONS if item.key == key)
    return BrinkHomeBinarySensorEntity(client, coordinator, 101, description)


def _number_sensor(
    client: MagicMock, coordinator: MagicMock, parameter_key: str
) -> BrinkHomeNumberEntity:
    """Instantiate a writable number without needing a running Home Assistant."""
    description = BrinkNumberEntityDescription(
        key=parameter_key, parameter_key=parameter_key
    )
    return BrinkHomeNumberEntity(client, coordinator, 101, description)


def test_upstream_binary_sensor_identity_survives_upgrade() -> None:
    """Retain existing gateway/filter IDs and avoid collisions with new sensors."""
    client, coordinator, _ = _dependencies({PARAM_FILTER_STATUS: {"value": "1"}})
    assert _binary_sensor("gateway_status", client, coordinator).unique_id == (
        f"{DOMAIN}_101_online"
    )
    assert _binary_sensor(PARAM_FILTER_STATUS, client, coordinator).unique_id == (
        f"{DOMAIN}_101_filter_status_binary_sensor"
    )
    assert _binary_sensor("device_online", client, coordinator).unique_id == (
        f"{DOMAIN}_101_device_online"
    )


@pytest.mark.parametrize(
    ("raw_state", "expected_on"),
    [
        ("2", True),
        ("online", True),
        ("1", False),
        ("offline", False),
        ("0", False),
        ("unrecognized", None),
        (None, None),
    ],
)
def test_gateway_state_normalization(
    raw_state: str | None, expected_on: bool | None
) -> None:
    """Known gateway values map to connectivity, never an invented online state."""
    client, coordinator, _ = _dependencies(gateway_state=raw_state)
    sensor = _binary_sensor("gateway_status", client, coordinator)
    assert sensor.is_on is expected_on


@pytest.mark.parametrize("permission", [None, False, True, 0, 1, 2, 4, "3", "bad"])
def test_vendor_writability_requires_explicit_integer_permission(
    permission: object,
) -> None:
    """A vendor value ID alone never authorizes changing the appliance."""
    parameter = {"read_write": permission, "value_id": 123}
    assert is_parameter_writable(parameter) is False
    assert writable_value_id(parameter) is None


@pytest.mark.parametrize("bad_id", [None, False, True, 0, -5, "not-an-id"])
def test_vendor_write_rejects_invalid_ids(bad_id: object) -> None:
    """Reject malformed or nonpositive vendor IDs without an API request."""
    assert writable_value_id({"read_write": 3, "value_id": bad_id}) is None


def test_signed_finite_device_bounds() -> None:
    """Allow legitimate negative ranges but reject missing or non-finite limits."""
    assert finite_parameter_bounds({"min_value": -3, "max_value": 10}) == (-3, 10)
    assert finite_parameter_bounds({"min_value": None, "max_value": 10}) is None
    assert finite_parameter_bounds({"min_value": float("nan"), "max_value": 10}) is None


@pytest.mark.parametrize("access", [None, 1, 2, "3", True, 4])
async def test_select_denies_non_writable_parameters(access: object) -> None:
    """No select action may reach the API without an explicit writable flag."""
    client, coordinator, parameter = _parameter_for_select(access)
    select = BrinkHomeSelectEntity(
        client,
        coordinator,
        101,
        BrinkSelectEntityDescription(key="valve_control", parameter_key="valve_control"),
    )
    with pytest.raises(HomeAssistantError) as error:
        await select._async_write_value("1")
    assert error.value.translation_key == "parameter_unavailable"
    assert parameter["value"] == "0"
    client.write_parameters.assert_not_awaited()


def _parameter_for_select(
    access: object,
) -> tuple[MagicMock, MagicMock, dict[str, object]]:
    """Return a synthetic select parameter and its device dependencies."""
    parameter: dict[str, object] = {
        "value": "0",
        "value_id": 123,
        "read_write": access,
    }
    client, coordinator, _ = _dependencies({"valve_control": parameter})
    return client, coordinator, parameter


@pytest.mark.parametrize("access", [None, 0, "3", True, 4])
async def test_number_denies_non_writable_parameters(access: object) -> None:
    """Reject an unauthorized number write without mutating cached data."""
    parameter: dict[str, object] = {
        "value": "0",
        "value_id": 123,
        "read_write": access,
        "min_value": -5,
        "max_value": 5,
    }
    client, coordinator, _ = _dependencies({"bypass_temperature": parameter})
    entity = _number_sensor(client, coordinator, "bypass_temperature")
    with pytest.raises(HomeAssistantError) as error:
        await entity.async_set_native_value(1.0)
    assert error.value.translation_key == "parameter_unavailable"
    assert parameter["value"] == "0"
    client.write_parameters.assert_not_awaited()


@pytest.mark.parametrize("requested", [float("nan"), float("inf"), -6, 6, True])
async def test_number_denies_nonfinite_and_out_of_range(
    requested: object,
) -> None:
    """Protect against non-finite, invalid and oversized numeric input."""
    parameter: dict[str, object] = {
        "value": "0",
        "value_id": 123,
        "read_write": 3,
        "min_value": -5,
        "max_value": 5,
    }
    client, coordinator, _ = _dependencies({"bypass_temperature": parameter})
    entity = _number_sensor(client, coordinator, "bypass_temperature")
    with pytest.raises(HomeAssistantError) as error:
        await entity.async_set_native_value(requested)
    assert error.value.translation_key == "value_out_of_range"
    client.write_parameters.assert_not_awaited()


async def test_signed_number_write_remains_valid() -> None:
    """Signed vendor values must remain functional on writable parameters."""
    parameter: dict[str, object] = {
        "value": "0",
        "value_id": 123,
        "read_write": 3,
        "min_value": -5,
        "max_value": 5,
        "decimals": 0,
    }
    client, coordinator, _ = _dependencies({"bypass_temperature": parameter})
    entity = _number_sensor(client, coordinator, "bypass_temperature")
    await entity.async_set_native_value(-2)
    client.write_parameters.assert_awaited_once_with(101, [(123, "-2")])
    assert parameter["value"] == "-2"


@pytest.mark.parametrize("failure", [TimeoutError("synthetic timeout"), OSError("test")])
async def test_failed_number_write_does_not_mutate_cache(failure: Exception) -> None:
    """A rejected/uncertain vendor write must not be published as confirmed."""
    parameter: dict[str, object] = {
        "value": "0",
        "value_id": 123,
        "read_write": 3,
        "min_value": -5,
        "max_value": 5,
    }
    client, coordinator, _ = _dependencies({"bypass_temperature": parameter})
    client.write_parameters.side_effect = failure
    entity = _number_sensor(client, coordinator, "bypass_temperature")
    with pytest.raises(type(failure)):
        await entity.async_set_native_value(2)
    assert parameter["value"] == "0"
    coordinator.async_set_updated_data.assert_not_called()


@pytest.mark.parametrize(
    "status", [None, "bad", True, False, 0, "0", -1, "2"]
)
def test_co2_number_availability_is_safe_for_missing_status(
    status: object,
) -> None:
    """Incomplete eBus status must make CO2 configuration unavailable."""
    parameters = {
        "co2_sensor_1_min_ppm": {"value": "600", "value_state": 1},
        "ebus_co2_sensor_status": {"value": status},
    }
    client, coordinator, _ = _dependencies(parameters)
    entity = _number_sensor(client, coordinator, "co2_sensor_1_min_ppm")
    assert entity.available is False


def test_co2_availability_recovers_and_checks_own_parameter_state() -> None:
    """A sensor becomes available on valid status and a non-invalid value."""
    parameters = {
        "co2_sensor_1_min_ppm": {"value": "600", "value_state": 1},
        "ebus_co2_sensor_status": {"value": "1"},
    }
    client, coordinator, _ = _dependencies(parameters)
    entity = _number_sensor(client, coordinator, "co2_sensor_1_min_ppm")
    assert entity.available is True
    parameters["co2_sensor_1_min_ppm"]["value_state"] = 5
    assert entity.available is False


def test_invalid_normalized_sensor_value_state_is_not_created() -> None:
    """Honor the canonical value_state field when filtering unusable entities."""
    description = BrinkSensorDescription(
        key="synthetic_parameter", parameter_key="synthetic_parameter"
    )
    _, _, device = _dependencies(
        {"synthetic_parameter": {"value": "1", "value_state": 5}}
    )
    assert _should_create_sensor(device, description) is False


async def test_unknown_vendor_fields_are_not_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Do not expose unknown parameter keys, names or values in any log level."""
    secrets = (
        "synthetic-private-key-secret",
        "synthetic-private-name-secret",
        "synthetic-private-value-secret",
    )
    client, coordinator, _ = _dependencies(
        {
            secrets[0]: {
                "name": secrets[1],
                "value": secrets[2],
                "options": [{"label": "synthetic-private-label-secret"}],
            }
        }
    )
    entry = MagicMock(entry_id="synthetic-entry")
    hass = MagicMock()
    hass.data = {DOMAIN: {entry.entry_id: {"client": client, "coordinator": coordinator}}}
    with caplog.at_level(logging.DEBUG):
        await async_setup_entry(hass, entry, MagicMock())
    for secret in (*secrets, "synthetic-private-label-secret"):
        assert secret not in caplog.text


def test_public_parameter_attributes_do_not_dump_vendor_payloads() -> None:
    """Retain supported state diagnostics, not raw device IDs/names/options."""
    secret = "synthetic-private-parameter-secret"
    parameter: dict[str, object] = {
        "name": secret,
        "raw_name": secret,
        "value": secret,
        "value_id": 123,
        "numeric_id": 222,
        "default_value": secret,
        "options": [{"label": secret}],
        "value_state": 1,
        "read_write": 3,
    }
    client, coordinator, _ = _dependencies(
        {
            "filter_status": dict(parameter),
            "valve_control": dict(parameter),
            "bypass_temperature": dict(parameter),
        }
    )
    entities = (
        _binary_sensor(PARAM_FILTER_STATUS, client, coordinator),
        BrinkHomeSelectEntity(
            client,
            coordinator,
            101,
            BrinkSelectEntityDescription(key="valve_control", parameter_key="valve_control"),
        ),
        _number_sensor(client, coordinator, "bypass_temperature"),
    )
    for entity in entities:
        attributes = entity.extra_state_attributes
        assert secret not in str(attributes)
        assert "value_id" not in attributes
        assert "read_write" in attributes
