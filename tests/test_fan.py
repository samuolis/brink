"""Regression tests for isolated fan presets and snapshot-dependent capacity."""

from __future__ import annotations

import logging
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import EntityPlatform

from custom_components.brink_ventilation.const import (
    DOMAIN,
    PARAM_OPERATING_MODE,
    PARAM_VENTILATION_LEVEL,
)
from custom_components.brink_ventilation.coordinator import BrinkCoordinator
from custom_components.brink_ventilation.fan import (
    BrinkHomeBaseFanEntity,
    BrinkHomeLevelFanEntity,
    BrinkHomeVentilationFanEntity,
)
from custom_components.brink_ventilation.models import BrinkDeviceData
from tests.ha_test_support import MockConfigEntry


def _device(
    system_id: int = 101, *, capacity: object = 400, level: object = "3"
) -> BrinkDeviceData:
    """Build a synthetic system with complete writable airflow metadata."""
    return BrinkDeviceData(
        api_is_online=True,
        system_id=system_id,
        name="Synthetic unit",
        internal_name="Synthetic unit",
        model="Flair",
        serial_number=None,
        gateway_state="online",
        gateway_type_id=3,
        device_is_online=True,
        ip_address=None,
        dns_server=None,
        sw_version=None,
        alerts=[],
        parameters={
            PARAM_VENTILATION_LEVEL: {
                "value": level,
                "value_id": 2000,
                "read_write": 3,
            },
            PARAM_OPERATING_MODE: {"value": "0", "value_id": 2001, "read_write": 3},
            "ventilation_mode_0_airflow": {
                "value": "50",
                "min_value": 0,
                "max_value": capacity,
                "read_write": 3,
                "value_id": 1000,
            },
            "ventilation_mode_1_airflow": {
                "value": "100",
                "min_value": 0,
                "max_value": capacity,
                "read_write": 3,
                "value_id": 1001,
            },
            "ventilation_mode_2_airflow": {
                "value": "200",
                "min_value": 0,
                "max_value": capacity,
                "read_write": 3,
                "value_id": 1002,
            },
            "ventilation_mode_3_airflow": {
                "value": capacity,
                "min_value": 0,
                "max_value": capacity,
                "read_write": 3,
                "value_id": 1003,
            },
        },
    )


def _client_and_coordinator(
    data: dict[int, BrinkDeviceData] | None,
) -> tuple[MagicMock, MagicMock]:
    """Mock transport and coordinator scheduling without replacing entity logic."""
    client = MagicMock()
    client.write_parameters = AsyncMock()
    coordinator = MagicMock(data=data, last_update_success=True)
    coordinator.async_request_refresh = AsyncMock()
    return client, coordinator


def test_preset_list_mutation_is_isolated() -> None:
    """A caller's edited choices must not alter this or another fan's presets."""
    client, coordinator = _client_and_coordinator({101: _device(), 102: _device(102)})
    first_fan = BrinkHomeVentilationFanEntity(client, coordinator, 101)
    second_fan = BrinkHomeLevelFanEntity(client, coordinator, 102)
    expected = ["automatic", "manual", "holiday", "party", "night_ventilation"]
    returned_modes = first_fan.preset_modes
    try:
        returned_modes.clear()
        assert first_fan.preset_modes == expected
        assert second_fan.preset_modes == expected
    finally:
        returned_modes[:] = expected


@pytest.mark.parametrize("initial_data", [None, {}])
@pytest.mark.parametrize(
    "fan_type", [BrinkHomeVentilationFanEntity, BrinkHomeLevelFanEntity]
)
def test_fan_handles_an_empty_snapshot(
    initial_data: dict[int, BrinkDeviceData] | None,
    fan_type: type[BrinkHomeBaseFanEntity],
) -> None:
    """Both fans remain safely unavailable before a device snapshot exists."""
    client, coordinator = _client_and_coordinator(initial_data)
    fan = fan_type(client, coordinator, 101)
    assert fan.percentage is None
    assert fan.werkt_percentage is None
    assert fan.available is False
    assert isinstance(fan.extra_state_attributes, dict)


@pytest.mark.parametrize("initial_data", [None, {}])
async def test_capacity_recovers_before_percentage_reads_and_writes(
    initial_data: dict[int, BrinkDeviceData] | None,
) -> None:
    """Recover a 400 m³/h fan as 100%, then write 200 m³/h for a 50% request."""
    client, coordinator = _client_and_coordinator(initial_data)
    fan = BrinkHomeVentilationFanEntity(client, coordinator, 101)
    fan.async_write_ha_state = MagicMock()
    coordinator.data = {101: _device()}

    assert fan.available is True
    assert fan.percentage == 100
    assert fan.werkt_percentage == 100
    await fan.async_set_percentage(50)
    assert client.write_parameters.await_args_list[0].args == (101, [(1002, "200")])


@pytest.mark.parametrize(
    "level", [None, "invalid", "", True, 1.5, float("nan"), float("inf"), -1, 5]
)
@pytest.mark.parametrize(
    "fan_type", [BrinkHomeVentilationFanEntity, BrinkHomeLevelFanEntity]
)
def test_unknown_level_does_not_raise_or_invent_airflow(
    level: object, fan_type: type[BrinkHomeBaseFanEntity]
) -> None:
    """Keep the level unknown and omit level-dependent attributes."""
    client, coordinator = _client_and_coordinator({101: _device(level=level)})
    fan = fan_type(client, coordinator, 101)
    assert fan.percentage is None
    assert fan.werkt_percentage is None
    assert fan.is_on is None
    assert "airflow" not in fan.extra_state_attributes


@pytest.mark.parametrize(
    "fan_type", [BrinkHomeVentilationFanEntity, BrinkHomeLevelFanEntity]
)
def test_missing_level_is_unknown(fan_type: type[BrinkHomeBaseFanEntity]) -> None:
    """Do not substitute level zero when an otherwise present parameter omits value."""
    device = _device()
    device.parameters[PARAM_VENTILATION_LEVEL].pop("value")
    client, coordinator = _client_and_coordinator({101: device})
    fan = fan_type(client, coordinator, 101)
    assert fan.percentage is None
    assert fan.werkt_percentage is None
    assert fan.is_on is None
    assert "airflow" not in fan.extra_state_attributes


@pytest.mark.parametrize("preset", ["manual", "Manual"])
@pytest.mark.parametrize(
    "fan_type", [BrinkHomeVentilationFanEntity, BrinkHomeLevelFanEntity]
)
async def test_preset_mutation_does_not_change_valid_choices_or_raw_writes(
    preset: str, fan_type: type[BrinkHomeBaseFanEntity]
) -> None:
    """Retain canonical and legacy inputs, translated choices, and numeric writes."""
    client, coordinator = _client_and_coordinator({101: _device()})
    fan = fan_type(client, coordinator, 101)
    returned_modes = fan.preset_modes
    returned_modes.remove("manual")
    await fan.async_set_preset_mode(preset)
    assert fan.preset_mode == "manual"
    assert fan.preset_mode in fan.preset_modes
    client.write_parameters.assert_awaited_once_with(101, [(2001, "1")])


@pytest.mark.parametrize("initial_capacity", [300, 300.0, "300"])
async def test_capacity_updates_after_normal_initialization(
    initial_capacity: object,
) -> None:
    """Honor changed limits on subsequent snapshots rather than the first one."""
    client, coordinator = _client_and_coordinator(
        {101: _device(capacity=initial_capacity)}
    )
    fan = BrinkHomeVentilationFanEntity(client, coordinator, 101)
    fan.async_write_ha_state = MagicMock()
    assert fan.percentage == 100

    coordinator.data = {101: _device(capacity=400)}
    assert fan.percentage == 100
    await fan.async_set_percentage(50)
    assert client.write_parameters.await_args_list[0].args == (101, [(1002, "200")])

    client.write_parameters.reset_mock()
    coordinator.data = {101: _device(capacity=600)}
    assert fan.percentage == 100
    await fan.async_set_percentage(50)
    assert client.write_parameters.await_args_list[0].args == (101, [(1003, "300")])


@pytest.mark.parametrize(("airflow", "value_id"), [(100, 1001), (150, 1002)])
@pytest.mark.parametrize(
    "fan_type", [BrinkHomeVentilationFanEntity, BrinkHomeLevelFanEntity]
)
async def test_direct_airflow_preserves_the_requested_integer_value(
    airflow: int, value_id: int, fan_type: type[BrinkHomeBaseFanEntity]
) -> None:
    """Write exact m³/h values without rounding through a percentage first."""
    client, coordinator = _client_and_coordinator({101: _device()})
    fan = fan_type(client, coordinator, 101)
    fan.async_write_ha_state = MagicMock()
    await fan.async_set_airflow(airflow)
    assert client.write_parameters.await_args_list[0].args == (
        101,
        [(value_id, str(airflow))],
    )


@pytest.mark.parametrize(
    "capacity",
    [None, 0, -1, True, 400.5, "bad", "nan", "inf", float("nan"), float("inf")],
)
@pytest.mark.parametrize(
    ("fan_type", "method_name"),
    [
        (BrinkHomeVentilationFanEntity, "async_set_percentage"),
        (BrinkHomeVentilationFanEntity, "async_set_airflow"),
        (BrinkHomeLevelFanEntity, "async_set_airflow"),
    ],
)
async def test_unusable_capacity_blocks_airflow_writes(
    capacity: object, fan_type: type[BrinkHomeBaseFanEntity], method_name: str
) -> None:
    """Reject unknown/non-finite bounds before writing either device parameter."""
    client, coordinator = _client_and_coordinator({101: _device(capacity=capacity)})
    fan = fan_type(client, coordinator, 101)
    assert fan.werkt_percentage is None
    if isinstance(fan, BrinkHomeVentilationFanEntity):
        assert fan.percentage is None
    with pytest.raises(HomeAssistantError) as caught:
        await getattr(fan, method_name)(50)
    assert caught.value.translation_domain == DOMAIN
    assert caught.value.translation_key == "airflow_parameter_unavailable"
    assert caught.value.translation_placeholders == {"level": "3"}
    client.write_parameters.assert_not_awaited()


@pytest.mark.parametrize("missing_parameter", [True, False])
async def test_missing_capacity_is_unknown_without_a_300_cubic_metre_guess(
    missing_parameter: bool,
) -> None:
    """Keep missing capacity metadata unknown instead of assuming a Flair 300."""
    device = _device()
    if missing_parameter:
        device.parameters.pop("ventilation_mode_3_airflow")
    else:
        device.parameters["ventilation_mode_3_airflow"].pop("max_value")
    client, coordinator = _client_and_coordinator({101: device})
    fan = BrinkHomeVentilationFanEntity(client, coordinator, 101)
    assert fan.percentage is None
    with pytest.raises(HomeAssistantError):
        await fan.async_set_percentage(50)
    client.write_parameters.assert_not_awaited()


@pytest.mark.parametrize("data", [None, {}])
@pytest.mark.parametrize(
    ("fan_type", "method_name"),
    [
        (BrinkHomeVentilationFanEntity, "async_set_percentage"),
        (BrinkHomeVentilationFanEntity, "async_set_airflow"),
        (BrinkHomeLevelFanEntity, "async_set_airflow"),
    ],
)
async def test_missing_device_blocks_airflow_writes(
    data: dict[int, BrinkDeviceData] | None,
    fan_type: type[BrinkHomeBaseFanEntity],
    method_name: str,
) -> None:
    """Report the missing device and leave the transport untouched."""
    client, coordinator = _client_and_coordinator(data)
    fan = fan_type(client, coordinator, 101)
    with pytest.raises(HomeAssistantError) as caught:
        await getattr(fan, method_name)(50)
    assert caught.value.translation_key == "device_unavailable"
    client.write_parameters.assert_not_awaited()


@pytest.mark.parametrize(
    "airflow", [None, "invalid", -1, True, float("nan"), float("inf"), 401]
)
def test_invalid_airflow_does_not_escape_as_a_percentage(airflow: object) -> None:
    """Keep unusable and out-of-range airflow readings unknown."""
    device = _device(level="1")
    device.parameters["ventilation_mode_1_airflow"]["value"] = airflow
    client, coordinator = _client_and_coordinator({101: device})
    fan = BrinkHomeVentilationFanEntity(client, coordinator, 101)
    assert fan.percentage is None
    assert fan.werkt_percentage is None


@pytest.mark.parametrize(
    ("airflow", "expected"), [(0, 0), ("0", 0), (150, 38), (150.5, 38), (400, 100)]
)
def test_valid_airflow_including_zero_is_preserved(
    airflow: object, expected: int
) -> None:
    """Report valid zero and numeric airflow using the current 400 m³/h capacity."""
    device = _device(level="1")
    device.parameters["ventilation_mode_1_airflow"]["value"] = airflow
    client, coordinator = _client_and_coordinator({101: device})
    fan = BrinkHomeVentilationFanEntity(client, coordinator, 101)
    assert fan.percentage == expected
    assert fan.werkt_percentage == expected


@pytest.mark.parametrize(
    "fan_type", [BrinkHomeVentilationFanEntity, BrinkHomeLevelFanEntity]
)
def test_external_cn1_does_not_become_a_percentage_above_100(
    fan_type: type[BrinkHomeBaseFanEntity],
) -> None:
    """Keep externally controlled level four readable without mapping it to 150%."""
    client, coordinator = _client_and_coordinator({101: _device(level="4")})
    fan = fan_type(client, coordinator, 101)
    assert fan.percentage is None
    assert fan.is_on is True


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_real_fan_state_recovers_and_writes_the_current_capacity(
    hass: HomeAssistant,
) -> None:
    """Recover an unavailable entity as 100%, then expose 50% after a 200 m³/h write."""
    client, _ = _client_and_coordinator(None)
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    coordinator = BrinkCoordinator(hass, entry, client, scan_interval=60)
    coordinator.async_request_refresh = AsyncMock()
    fan = BrinkHomeVentilationFanEntity(client, coordinator, 101)
    fan.entity_id = "fan.synthetic_airflow"
    platform = EntityPlatform(
        hass=hass,
        logger=logging.getLogger(__name__),
        domain="fan",
        platform_name=DOMAIN,
        platform=None,
        scan_interval=timedelta(seconds=60),
        entity_namespace=None,
    )
    platform.config_entry = entry
    try:
        await platform.async_add_entities([fan])
        unavailable_state = hass.states.get(fan.entity_id)
        assert unavailable_state is not None
        assert unavailable_state.state == STATE_UNAVAILABLE

        coordinator.async_set_updated_data({101: _device()})
        await hass.async_block_till_done()
        recovered_state = hass.states.get(fan.entity_id)
        assert recovered_state is not None
        assert recovered_state.attributes["percentage"] == 100

        await fan.async_set_percentage(50)
        await hass.async_block_till_done()
        updated_state = hass.states.get(fan.entity_id)
        assert updated_state is not None
        assert updated_state.attributes["percentage"] == 50
        assert client.write_parameters.await_args_list[0].args == (101, [(1002, "200")])
    finally:
        await platform.async_reset()
        await coordinator.async_shutdown()


@pytest.mark.parametrize(
    "entity_class", (BrinkHomeLevelFanEntity, BrinkHomeVentilationFanEntity)
)
@pytest.mark.parametrize(
    ("level_parameter", "expected_airflow", "expected_percentage"),
    (
        (None, None, None),
        ({}, None, None),
        ({"value": None}, None, None),
        ({"value": "invalid"}, None, None),
        ({"value": []}, None, None),
        ({"value": 0}, 30, 10),
        ({"value": "0"}, 30, 10),
        ({"value": "1"}, 90, 30),
        ({"value": "3"}, 300, 100),
        ({"value": "4"}, 120, 40),
    ),
)
def test_level_dependent_state(
    entity_class: type[BrinkHomeLevelFanEntity | BrinkHomeVentilationFanEntity],
    level_parameter: dict[str, object] | None,
    expected_airflow: int | None,
    expected_percentage: int | None,
) -> None:
    """Keep unknown levels distinct from level zero and retain independent data."""
    parameters: dict[str, dict[str, object]] = {
        "ventilation_mode_0_airflow": {"value": 30},
        "ventilation_mode_1_airflow": {"value": 90},
        "ventilation_mode_3_airflow": {"value": 300, "max_value": 300},
        "ventilation_mode_4_airflow": {"value": 120},
        "supply_air_flow_setpoint": {"value": 75},
    }
    if level_parameter is not None:
        parameters["ventilation_level"] = {
            "name": "Ventilation level",
            "default_value": "1",
            "options": [{"label": "Low"}],
            **level_parameter,
        }
    device = BrinkDeviceData(
        api_is_online=True,
        system_id=101,
        name="Test device",
        internal_name="Test device",
        model="Flair 300",
        serial_number="test-device",
        gateway_state="online",
        gateway_type_id=3,
        device_is_online=True,
        ip_address=None,
        dns_server=None,
        sw_version=None,
        alerts=[],
        parameters=parameters,
    )
    coordinator = MagicMock(data={101: device})
    fan = entity_class(MagicMock(), coordinator, 101)

    assert fan.werkt_percentage == expected_percentage
    attributes = fan.extra_state_attributes
    if expected_airflow is None:
        assert "airflow" not in attributes
    else:
        assert attributes["airflow"] == expected_airflow
    assert attributes["airflow_setpont"] == 75
    if level_parameter is not None:
        assert "name" not in attributes
        assert "default_value" not in attributes
        assert "raw_options" not in attributes


def test_legacy_level_fan_unique_id_is_preserved() -> None:
    """Keep the registered identity of the original level-based fan."""
    client, coordinator = _client_and_coordinator({101: _device()})
    level_fan = BrinkHomeLevelFanEntity(client, coordinator, 101)
    airflow_fan = BrinkHomeVentilationFanEntity(client, coordinator, 101)
    assert level_fan.unique_id == f"{DOMAIN}_101_{PARAM_VENTILATION_LEVEL}_fan"
    assert airflow_fan.unique_id != level_fan.unique_id


@pytest.mark.parametrize(
    ("airflow", "expected_on"), [(0, False), (1, True), (30, True)]
)
def test_level_zero_airflow_is_not_necessarily_off(
    airflow: int, expected_on: bool
) -> None:
    """Report low positive airflow as running even at level zero."""
    device = _device(capacity=300, level="0")
    device.parameters["ventilation_mode_0_airflow"]["value"] = str(airflow)
    client, coordinator = _client_and_coordinator({101: device})
    continuous = BrinkHomeVentilationFanEntity(client, coordinator, 101)
    discrete = BrinkHomeLevelFanEntity(client, coordinator, 101)
    assert continuous.is_on is expected_on
    assert discrete.is_on is False


@pytest.mark.parametrize("invalid_value", [None, True, -1, "broken", float("nan")])
def test_level_zero_invalid_airflow_is_unknown(invalid_value: object) -> None:
    """Do not report off when the level-zero airflow is not valid data."""
    device = _device(capacity=300, level="0")
    device.parameters["ventilation_mode_0_airflow"]["value"] = invalid_value
    client, coordinator = _client_and_coordinator({101: device})
    fan = BrinkHomeVentilationFanEntity(client, coordinator, 101)
    assert fan.is_on is None


async def test_continuous_turn_off_writes_zero_airflow() -> None:
    """Reset the level-zero airflow setpoint when switching the fan off."""
    client, coordinator = _client_and_coordinator(
        {101: _device(capacity=300, level="0")}
    )
    fan = BrinkHomeVentilationFanEntity(client, coordinator, 101)
    fan.async_write_ha_state = MagicMock()
    await fan.async_turn_off()
    assert client.write_parameters.await_args_list[0].args == (101, [(1000, "0")])
    assert client.write_parameters.await_args_list[1].args[-1][-1] == (2000, "0")
    assert fan.is_on is False


@pytest.mark.parametrize("as_percentage", [False, True])
async def test_airflow_level_selection_respects_device_bounds(
    as_percentage: bool,
) -> None:
    """Use level three if level two cannot supply the requested 180 m³/h."""
    device = _device(capacity=300)
    device.parameters["ventilation_mode_2_airflow"]["max_value"] = 150
    client, coordinator = _client_and_coordinator({101: device})
    fan = BrinkHomeVentilationFanEntity(client, coordinator, 101)
    fan.async_write_ha_state = MagicMock()
    if as_percentage:
        await fan.async_set_percentage(60)
    else:
        await fan.async_set_airflow(180)
    assert client.write_parameters.await_args_list[0].args == (101, [(1003, "180")])


async def test_unreachable_airflow_target_has_no_partial_device_write() -> None:
    """Reject an unsupported flow before issuing any device commands."""
    device = _device(capacity=300)
    device.parameters["ventilation_mode_2_airflow"]["max_value"] = 150
    device.parameters["ventilation_mode_3_airflow"]["min_value"] = 200
    client, coordinator = _client_and_coordinator({101: device})
    fan = BrinkHomeVentilationFanEntity(client, coordinator, 101)
    with pytest.raises(HomeAssistantError) as caught:
        await fan.async_set_airflow(180)
    assert caught.value.translation_key == "airflow_parameter_unavailable"
    client.write_parameters.assert_not_awaited()


@pytest.mark.parametrize("invalid_target", [-1, 301, True, 42.5, float("nan")])
async def test_invalid_airflow_target_is_not_clamped(invalid_target: object) -> None:
    """Do not silently clip invalid requested airflow rates."""
    client, coordinator = _client_and_coordinator({101: _device(capacity=300)})
    fan = BrinkHomeVentilationFanEntity(client, coordinator, 101)
    with pytest.raises(HomeAssistantError) as caught:
        await fan.async_set_airflow(invalid_target)
    assert caught.value.translation_key == "value_out_of_range"
    client.write_parameters.assert_not_awaited()


@pytest.mark.parametrize("invalid_percent", [-1, 101, True, 50.5])
async def test_invalid_percentage_is_rejected(invalid_percent: object) -> None:
    """Reject invalid percentage input before writing to the Brink API."""
    client, coordinator = _client_and_coordinator({101: _device(capacity=300)})
    fan = BrinkHomeVentilationFanEntity(client, coordinator, 101)
    with pytest.raises(HomeAssistantError):
        await fan.async_set_percentage(invalid_percent)
    client.write_parameters.assert_not_awaited()


@pytest.mark.parametrize("access", [0, 1, None, 2, "3", True, [], 3.0])
async def test_non_writable_airflow_is_skipped_and_rejected(access: object) -> None:
    """Selection skips unsupported access and direct writes reject it."""
    device = _device(capacity=300)
    device.parameters["ventilation_mode_1_airflow"]["read_write"] = access
    client, coordinator = _client_and_coordinator({101: device})
    fan = BrinkHomeVentilationFanEntity(client, coordinator, 101)
    assert fan._select_airflow_level(100) == 2
    with pytest.raises(HomeAssistantError) as caught:
        await fan._set_airflow_for_level(1, 100)
    assert caught.value.translation_key == "airflow_parameter_unavailable"
    client.write_parameters.assert_not_awaited()


@pytest.mark.parametrize(
    "invalid_metadata", ["missing", "bounds", "access", "value_id"]
)
async def test_turn_off_requires_valid_level_zero(invalid_metadata: str) -> None:
    """Never substitute level one when level zero cannot accept zero airflow."""
    device = _device(capacity=300)
    parameter = device.parameters["ventilation_mode_0_airflow"]
    if invalid_metadata == "missing":
        del device.parameters["ventilation_mode_0_airflow"]
    elif invalid_metadata == "bounds":
        parameter["min_value"] = 1
    elif invalid_metadata == "access":
        parameter["read_write"] = 1
    else:
        parameter["value_id"] = None
    client, coordinator = _client_and_coordinator({101: device})
    fan = BrinkHomeVentilationFanEntity(client, coordinator, 101)
    with pytest.raises(HomeAssistantError) as caught:
        await fan.async_turn_off()
    assert caught.value.translation_key == "airflow_parameter_unavailable"
    client.write_parameters.assert_not_awaited()
