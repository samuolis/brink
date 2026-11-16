"""Regression tests for Brink Renovent Excellent 400 support."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers import entity_platform

from custom_components.brink_ventilation.const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
)
from custom_components.brink_ventilation.core.brink_home_cloud import BrinkHomeCloud
from custom_components.brink_ventilation.fan import (
    BrinkHomeLevelFanEntity,
    BrinkHomeVentilationFanEntity,
    async_setup_entry as async_setup_fan_entry,
)
from custom_components.brink_ventilation.models import BrinkDeviceData
from custom_components.brink_ventilation.number import (
    BrinkHomeNumberEntity,
    async_setup_entry as async_setup_number_entry,
)
from custom_components.brink_ventilation.select import (
    BrinkHomeSelectEntity,
    async_setup_entry as async_setup_select_entry,
)
from custom_components.brink_ventilation.sensor import (
    async_setup_entry as async_setup_sensor_entry,
)


def _synthetic_excellent_400_nav_items(
    *, use_unknown_names: bool = False
) -> list[dict[str, object]]:
    """Build synthetic Excellent 400 uiDescription items without real account data."""

    def _name(raw_name: str) -> str:
        return "Unmapped vendor label" if use_unknown_names else raw_name

    return [
        {
            "parameterGroups": [
                {
                    "parameters": [
                        {
                            "id": 4007,
                            "name": _name("Lüftungsstufe_oldAddress"),
                            "value": "1",
                            "valueId": 1001,
                            "valueState": 0,
                            "readWrite": 3,
                            "controlType": 0,
                            "listItems": [
                                {"value": "0", "translationId": "Stufe 0"},
                                {"value": "1", "translationId": "Stufe 1"},
                                {"value": "2", "translationId": "Stufe 2"},
                                {"value": "3", "translationId": "Stufe 3"},
                            ],
                        },
                        {
                            "id": 4013,
                            "name": _name("Soll-Wert Luftdurchsatz Zuluft"),
                            "value": "115",
                            "valueId": 1002,
                            "valueState": 0,
                            "readWrite": 1,
                            "controlType": 6,
                        },
                        {
                            "id": 4014,
                            "name": "Ist-Wert Luftdurchsatz Zuluft",
                            "value": "115",
                            "valueId": 1003,
                            "valueState": 0,
                            "readWrite": 1,
                            "controlType": 6,
                        },
                        {
                            "id": 4016,
                            "name": _name("Zuluftdruck"),
                            "value": "38.0",
                            "valueId": 1004,
                            "valueState": 0,
                            "readWrite": 1,
                            "controlType": 6,
                        },
                        {
                            "id": 4019,
                            "name": _name("Soll-Wert Luftdurchsatz Abluft"),
                            "value": "115",
                            "valueId": 1005,
                            "valueState": 0,
                            "readWrite": 1,
                            "controlType": 6,
                        },
                        {
                            "id": 4020,
                            "name": "Ist-Wert Luftdurchsatz Abluft",
                            "value": "115",
                            "valueId": 1006,
                            "valueState": 0,
                            "readWrite": 1,
                            "controlType": 6,
                        },
                        {
                            "id": 4021,
                            "name": _name("Drehzahl Abluftventilator"),
                            "value": "2050",
                            "valueId": 1007,
                            "valueState": 0,
                            "readWrite": 1,
                            "controlType": 6,
                        },
                        {
                            "id": 4022,
                            "name": _name("Abluftdruck"),
                            "value": "126.0",
                            "valueId": 1008,
                            "valueState": 0,
                            "readWrite": 1,
                            "controlType": 6,
                        },
                        {
                            "id": 4031,
                            "name": _name("Leistung Vorheizregister"),
                            "value": "0",
                            "valueId": 1009,
                            "valueState": 0,
                            "readWrite": 1,
                            "controlType": 6,
                        },
                        {
                            "id": 4062,
                            "name": _name("Luftdurchsatz Stufe 0"),
                            "value": "50",
                            "valueId": 1010,
                            "valueState": 1,
                            "readWrite": 3,
                            "controlType": 6,
                            "minValue": 0,
                            "maxValue": 50,
                        },
                        {
                            "id": 4063,
                            "name": _name("Luftdurchsatz Stufe 1"),
                            "value": "115",
                            "valueId": 1011,
                            "valueState": 1,
                            "readWrite": 3,
                            "controlType": 6,
                            "minValue": 50,
                            "maxValue": 400,
                        },
                        {
                            "id": 4064,
                            "name": _name("Luftdurchsatz Stufe 2"),
                            "value": "160",
                            "valueId": 1012,
                            "valueState": 1,
                            "readWrite": 3,
                            "controlType": 6,
                            "minValue": 50,
                            "maxValue": 400,
                        },
                        {
                            "id": 4065,
                            "name": _name("Luftdurchsatz Stufe 3"),
                            "value": "400",
                            "valueId": 1013,
                            "valueState": 1,
                            "readWrite": 3,
                            "controlType": 6,
                            "minValue": 50,
                            "maxValue": 400,
                        },
                        {
                            "id": 4066,
                            "name": _name("Bypass-Temperatur"),
                            "value": "22.0",
                            "valueId": 1014,
                            "valueState": 1,
                            "readWrite": 3,
                            "controlType": 6,
                            "minValue": 15,
                            "maxValue": 35,
                        },
                        {
                            "id": 4067,
                            "name": _name("Bypass-Hysterese"),
                            "value": "2.0",
                            "valueId": 1015,
                            "valueState": 1,
                            "readWrite": 3,
                            "controlType": 6,
                            "minValue": 0,
                            "maxValue": 5,
                        },
                    ]
                }
            ]
        }
    ]


@pytest.mark.parametrize("use_unknown_names", [False, True])
async def test_excellent_400_parameters_enable_controls_and_sensors(
    use_unknown_names: bool,
) -> None:
    """Expose fan, select, number, and unique sensors for Excellent 400 devices."""
    parameters: dict[str, dict[str, object]] = {}
    BrinkHomeCloud._extract_parameters(
        _synthetic_excellent_400_nav_items(use_unknown_names=use_unknown_names),
        parameters,
    )
    device = BrinkDeviceData(
        api_is_online=True,
        system_id=101,
        name="Synthetic unit",
        internal_name="Synthetic unit",
        model="Excellent 400",
        serial_number=None,
        gateway_state="online",
        gateway_type_id=2,
        device_is_online=True,
        ip_address=None,
        dns_server=None,
        sw_version=None,
        alerts=[],
        parameters=parameters,
    )
    client = MagicMock(write_parameters=AsyncMock())
    coordinator = MagicMock(data={101: device}, last_update_success=True)
    coordinator.async_request_refresh = AsyncMock()
    entry = MagicMock(entry_id="synthetic-excellent-400")
    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            entry.entry_id: {
                DATA_CLIENT: client,
                DATA_COORDINATOR: coordinator,
            }
        }
    }

    fans: list[object] = []
    selects: list[BrinkHomeSelectEntity] = []
    numbers: list[BrinkHomeNumberEntity] = []
    sensors: list[object] = []

    with patch.object(
        entity_platform,
        "async_get_current_platform",
        return_value=MagicMock(),
    ):
        await async_setup_fan_entry(hass, entry, fans.extend)
    await async_setup_select_entry(hass, entry, selects.extend)
    await async_setup_number_entry(hass, entry, numbers.extend)
    await async_setup_sensor_entry(hass, entry, sensors.extend)

    assert len(fans) == 2
    airflow_fan = next(
        entity for entity in fans if isinstance(entity, BrinkHomeVentilationFanEntity)
    )
    level_fan = next(
        entity for entity in fans if isinstance(entity, BrinkHomeLevelFanEntity)
    )
    assert airflow_fan.available is True
    assert airflow_fan.percentage == 29
    assert level_fan.available is True
    assert level_fan.percentage == 33

    level_select = next(
        entity for entity in selects if entity.parameter_key == "ventilation_level"
    )
    assert level_select.options == ["level_0", "level_1", "level_2", "level_3"]
    assert level_select.current_option == "level_1"

    number_keys = {entity.parameter_key for entity in numbers}
    assert {
        "ventilation_mode_0_airflow",
        "ventilation_mode_1_airflow",
        "ventilation_mode_2_airflow",
        "ventilation_mode_3_airflow",
        "bypass_temperature",
        "bypass_hysteresis",
    } <= number_keys

    sensor_unique_ids = [entity.unique_id for entity in sensors]
    assert len(sensor_unique_ids) == len(set(sensor_unique_ids))

    percentage_sensor = next(
        entity for entity in sensors if entity.parameter_key == "ventilation_percentage"
    )
    assert percentage_sensor.available is True
    assert percentage_sensor.native_value == 29

    sound_sensor = next(
        entity for entity in sensors if entity.parameter_key == "cabinet_sound_power"
    )
    assert sound_sensor.native_value is not None
