"""Regression tests for Brink entity, option, and exception translations."""

from __future__ import annotations

import json
import re
from pathlib import Path
from string import Formatter
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import slugify

from custom_components.brink_ventilation.binary_sensor import BINARY_SENSOR_DESCRIPTIONS
from custom_components.brink_ventilation.const import DOMAIN
from custom_components.brink_ventilation.core.brink_home_cloud import BrinkHomeCloud
from custom_components.brink_ventilation.core.option_mapping import (
    build_option_state_map,
)
from custom_components.brink_ventilation.fan import (
    FAN_DESCRIPTION,
    VENTILATION_FAN_DESCRIPTION,
    BrinkHomeLevelFanEntity,
)
from custom_components.brink_ventilation.models import BrinkDeviceData
from custom_components.brink_ventilation.number import (
    NUMBER_DESCRIPTIONS,
    BrinkHomeNumberEntity,
    BrinkNumberEntityDescription,
)
from custom_components.brink_ventilation.select import (
    SELECT_DESCRIPTIONS,
    BrinkHomeSelectEntity,
    BrinkSelectEntityDescription,
)
from custom_components.brink_ventilation.sensor import (
    SENSOR_DESCRIPTIONS,
    BrinkHomeSensorEntity,
)

LANGUAGES = ("en", "nl", "de")
TRANSLATIONS_PATH = (
    Path(__file__).resolve().parents[1] / "custom_components" / DOMAIN / "translations"
)
RUNTIME_OPTIONS = (
    ("valve_control", "Relaisausgang 1", "Relais output 1"),
    ("valve_control", "Relaisausgang 2", "Relais output 2"),
    ("valve_control", "Analoge Ausgabe 1", "Analog output 1"),
    ("valve_control", "Analoge Ausgabe 2", "analog output 2"),
    ("bypass_function", "Automatische_Funktion", "Auto mode"),
    ("bypass_function", "Bypass-Klappe_geschlossen", "Bypass closed"),
    ("bypass_function", "Bypass-Klappe_geöffnet", "Bypass open"),
    ("bypass_function", "Aus", "Off"),
    ("bypass_function", "Ein", "On"),
    ("supply_fan_control", "Constant_flow", "Constant flow"),
    ("supply_fan_control", "Constant_rpm", "Constant rpm"),
    ("supply_fan_control", "Off", "Off"),
    *(
        (f"cn{contact_number}_conditions", raw_label, expected_label)
        for contact_number in (1, 2)
        for raw_label, expected_label in (
            ("Nur Filter", "Only filtercondition"),
            ("Störbedingung", "Only faultcondition"),
            ("Filter-und Störbedingung", "Filter and fault condition"),
        )
    ),
    *(
        (f"contact_{contact_number}_{fan_kind}_fan_action", raw_label, expected_label)
        for contact_number in (1, 2)
        for fan_kind in ("supply", "exhaust")
        for raw_label, expected_label in (
            (
                "Zuluftventilator_aus"
                if fan_kind == "supply"
                else "Abluftventilator_aus",
                "Supply fan off" if fan_kind == "supply" else "Extract fan off",
            ),
            ("Absoluter_Mind.durchsatz_50_m³/h", "Min. ventilation 50 m³/h"),
            ("Luftdurchsatz_Stufe_1", "Air flow Level 1"),
            ("Luftdurchsatz_Stufe_2", "Air flow Level 2"),
            ("Luftdurchsatz_Stufe_3", "Air flow Level 3"),
            ("Max._Luftdurchsatz", "Max. air flow"),
            (
                "Keine_Ansteuerung_Zuluftventilator"
                if fan_kind == "supply"
                else "Keine_Ansteuerung_Abluftventilator",
                "No control supply fan"
                if fan_kind == "supply"
                else "No control extract fan",
            ),
        )
    ),
)


def _collision_parameter(
    cache_mode: str, labels: tuple[str, str] = ("Relay-1", "Relay 1")
) -> dict[str, Any]:
    """Build real extracted metadata with two conflicting options and one safe option."""
    parameters: dict[str, dict[str, Any]] = {}
    BrinkHomeCloud._extract_parameters(
        [
            {
                "parameterGroups": [
                    {
                        "parameters": [
                            {
                                "id": 16137,
                                "name": "Valve control",
                                "value": "1",
                                "valueId": 123,
                                "valueState": 1,
                                "listItems": [
                                    {"value": "0", "text": labels[0]},
                                    {"value": "1", "text": labels[1]},
                                    {"value": "2", "text": "Off"},
                                ],
                            }
                        ]
                    }
                ]
            }
        ],
        parameters,
    )
    parameter = parameters["valve_control"]
    if cache_mode != "normalized_cache":
        parameter.pop("option_state_map")
        parameter.pop("ambiguous_option_states")
    if cache_mode == "raw_cache":
        parameter["options"] = []
    elif cache_mode == "uncached":
        parameter.pop("options_map")
        parameter.pop("reverse_options_map")
    return parameter


def _load_translations(language: str) -> dict[str, Any]:
    """Load a shipped locale catalog."""
    return json.loads(
        (TRANSLATIONS_PATH / f"{language}.json").read_text(encoding="utf-8")
    )


def _flatten_catalog(catalog: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Flatten a catalog so shared omissions and placeholder drift are visible."""
    entries: dict[str, str] = {}
    for catalog_key, catalog_value in catalog.items():
        entry_key = f"{prefix}.{catalog_key}" if prefix else catalog_key
        if isinstance(catalog_value, dict):
            entries.update(_flatten_catalog(catalog_value, entry_key))
        else:
            assert isinstance(catalog_value, str) and catalog_value.strip(), entry_key
            entries[entry_key] = catalog_value
    return entries


def _create_entity_dependencies(
    parameters: dict[str, dict[str, Any]],
) -> tuple[MagicMock, MagicMock]:
    """Create a device and async client without network or Home Assistant setup."""
    device = BrinkDeviceData(
        api_is_online=True,
        system_id=101,
        name="Brink",
        internal_name="Brink",
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
    # Synthetic writable fixtures must explicitly advertise vendor write access.
    for parameter in parameters.values():
        if parameter.get("value_id") is not None:
            parameter.setdefault("read_write", 3)
    client = MagicMock(write_parameters=AsyncMock())
    coordinator = MagicMock(
        data={101: device},
        last_update_success=True,
        async_request_refresh=AsyncMock(),
    )
    return client, coordinator


def _assert_translatable_error(
    error: HomeAssistantError,
    language: str,
    expected_key: str,
    expected_placeholders: dict[str, str] | None = None,
) -> None:
    """Verify the error metadata can render the complete localized message."""
    assert error.translation_domain == DOMAIN
    assert error.translation_key == expected_key
    assert error.translation_placeholders == expected_placeholders
    message = _load_translations(language)["exceptions"][expected_key]["message"]
    placeholder_names = {
        field_name
        for _, field_name, _, _ in Formatter().parse(message)
        if field_name is not None
    }
    assert placeholder_names == set(expected_placeholders or {})
    assert message.format_map(expected_placeholders or {})


@pytest.mark.parametrize("language", LANGUAGES)
def test_catalog_keys_and_placeholders_match_english(language: str) -> None:
    """Keep every shipped language complete and compatible with English placeholders."""
    english_entries = _flatten_catalog(_load_translations("en"))
    locale_entries = _flatten_catalog(_load_translations(language))
    assert locale_entries.keys() == english_entries.keys()
    for entry_key, locale_message in locale_entries.items():
        expected_fields = {
            field_name
            for _, field_name, _, _ in Formatter().parse(english_entries[entry_key])
            if field_name is not None
        }
        actual_fields = {
            field_name
            for _, field_name, _, _ in Formatter().parse(locale_message)
            if field_name is not None
        }
        assert actual_fields == expected_fields, entry_key


@pytest.mark.parametrize("language", LANGUAGES)
def test_state_translation_keys_follow_home_assistant_schema(language: str) -> None:
    """Reject state labels whose casing or punctuation prevents hassfest validation."""
    for entry_key in _flatten_catalog(_load_translations(language)):
        if ".state." in entry_key:
            state_key = entry_key.rsplit(".state.", 1)[1]
            assert re.fullmatch(r"[a-z0-9]+(?:[_-][a-z0-9]+)*", state_key), entry_key


@pytest.mark.parametrize("language", LANGUAGES)
def test_declared_entities_have_translated_names_and_states(language: str) -> None:
    """Catch names and fixed enum states missing from every language at once."""
    entity_catalog = _load_translations(language)["entity"]
    for platform, descriptions in (
        ("binary_sensor", BINARY_SENSOR_DESCRIPTIONS),
        ("fan", (FAN_DESCRIPTION, VENTILATION_FAN_DESCRIPTION)),
        ("number", NUMBER_DESCRIPTIONS),
        ("select", SELECT_DESCRIPTIONS),
        ("sensor", SENSOR_DESCRIPTIONS),
    ):
        for description in descriptions:
            translated_entity = entity_catalog[platform][description.translation_key]
            assert translated_entity["name"].strip()
            state_map = getattr(description, "value_map", None) or getattr(
                description, "label_map", None
            )
            for state_label in (state_map or {}).values():
                assert translated_entity["state"][slugify(state_label)].strip()
    assert entity_catalog["select"]["ventilation_level"]["state"]["cn1"]


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize(
    ("parameter_key", "raw_label", "expected_label"), RUNTIME_OPTIONS
)
@pytest.mark.asyncio
async def test_api_options_translate_without_changing_writes(
    language: str, parameter_key: str, raw_label: str, expected_label: str
) -> None:
    """Translate portal labels to stable states while preserving numeric device writes."""
    options = BrinkHomeCloud._extract_options(
        [{"value": 2, "translationId": raw_label, "isSelectable": True}]
    )
    client, coordinator = _create_entity_dependencies(
        {parameter_key: {"value": "2", "value_id": 123, "options": options}}
    )
    description = next(
        item for item in SELECT_DESCRIPTIONS if item.parameter_key == parameter_key
    )
    entity = BrinkHomeSelectEntity(client, coordinator, 101, description)
    expected_state = slugify(expected_label)
    assert entity.current_option == expected_state
    assert entity.options == [expected_state]
    translated_states = _load_translations(language)["entity"]["select"][parameter_key][
        "state"
    ]
    assert translated_states[expected_state].strip()
    await entity.async_select_option(expected_state)
    client.write_parameters.assert_awaited_once_with(101, [(123, "2")])


@pytest.mark.parametrize("option", ("manual", "Manual"))
@pytest.mark.asyncio
async def test_cached_options_accept_stable_and_legacy_inputs(option: str) -> None:
    """Retain cached reverse lookups when API labels differ from state keys."""
    client, coordinator = _create_entity_dependencies(
        {
            "operating_mode": {
                "value_id": 123,
                "value": "1",
                "options": [],
                "options_map": {"1": "Manual"},
                "reverse_options_map": {"Manual": "1"},
            }
        }
    )
    description = next(
        item for item in SELECT_DESCRIPTIONS if item.parameter_key == "operating_mode"
    )
    entity = BrinkHomeSelectEntity(client, coordinator, 101, description)
    assert entity.current_option == "manual"
    await entity.async_select_option(option)
    client.write_parameters.assert_awaited_once_with(101, [(123, "1")])


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("cache_mode", ("normalized_cache", "raw_cache", "uncached"))
@pytest.mark.parametrize("labels", (("Relay-1", "Relay 1"), ("Relay 1", "Relay 1")))
@pytest.mark.parametrize("option", ("relay_1", "Relay-1", "Relay 1"))
@pytest.mark.asyncio
async def test_ambiguous_option_states_never_write_a_device_value(
    language: str, cache_mode: str, labels: tuple[str, str], option: str
) -> None:
    """Reject colliding state keys and legacy labels before any device write."""
    parameter = _collision_parameter(cache_mode, labels)
    client, coordinator = _create_entity_dependencies({"valve_control": parameter})
    description = next(
        item for item in SELECT_DESCRIPTIONS if item.parameter_key == "valve_control"
    )
    entity = BrinkHomeSelectEntity(client, coordinator, 101, description)
    assert entity.options == ["off"]
    assert entity.current_option is None
    with pytest.raises(HomeAssistantError) as raised_error:
        await entity.async_select_option(option)
    _assert_translatable_error(
        raised_error.value,
        language,
        "ambiguous_option",
        {"option": option, "parameter": "Valve control"},
    )
    client.write_parameters.assert_not_awaited()


@pytest.mark.parametrize("cache_mode", ("normalized_cache", "raw_cache", "uncached"))
@pytest.mark.asyncio
async def test_safe_choice_remains_writable_alongside_ambiguous_choices(
    cache_mode: str,
) -> None:
    """Keep unambiguous options usable without exposing duplicate or misleading states."""
    parameter = _collision_parameter(cache_mode)
    client, coordinator = _create_entity_dependencies({"valve_control": parameter})
    description = next(
        item for item in SELECT_DESCRIPTIONS if item.parameter_key == "valve_control"
    )
    entity = BrinkHomeSelectEntity(client, coordinator, 101, description)
    await entity.async_select_option("off")
    client.write_parameters.assert_awaited_once_with(101, [(123, "2")])
    assert entity.current_option == "off"


@pytest.mark.asyncio
async def test_same_value_aliases_do_not_create_ambiguous_choices() -> None:
    """Collapse aliases safely when they resolve to the same raw device value."""
    options = [{"value": "1", "label": "Relay-1"}, {"value": "1", "label": "Relay 1"}]
    client, coordinator = _create_entity_dependencies(
        {"valve_control": {"value": "1", "value_id": 123, "options": options}}
    )
    description = next(
        item for item in SELECT_DESCRIPTIONS if item.parameter_key == "valve_control"
    )
    entity = BrinkHomeSelectEntity(client, coordinator, 101, description)
    assert entity.options == ["relay_1"]
    assert entity.current_option == "relay_1"
    await entity.async_select_option("relay_1")
    client.write_parameters.assert_awaited_once_with(101, [(123, "1")])


@pytest.mark.asyncio
async def test_fixed_label_maps_reject_normalization_collisions() -> None:
    """Validate fixed descriptions before a reverse dictionary can discard conflicts."""
    client, coordinator = _create_entity_dependencies(
        {"valve_control": {"value": "1", "value_id": 123}}
    )
    description = BrinkSelectEntityDescription(
        key="valve_control",
        parameter_key="valve_control",
        label_map={"0": "Relay-1", "1": "Relay 1", "2": "Off"},
    )
    entity = BrinkHomeSelectEntity(client, coordinator, 101, description)
    assert entity.options == ["off"]
    assert entity.current_option is None
    with pytest.raises(HomeAssistantError) as raised_error:
        await entity.async_select_option("relay_1")
    assert raised_error.value.translation_key == "ambiguous_option"
    client.write_parameters.assert_not_awaited()


def test_extracted_normalized_options_use_cached_mapping() -> None:
    """Keep indexed reads for normalized options on each coordinator snapshot."""
    parameter = _collision_parameter("normalized_cache")
    client, coordinator = _create_entity_dependencies({"valve_control": parameter})
    description = next(
        item for item in SELECT_DESCRIPTIONS if item.parameter_key == "valve_control"
    )
    entity = BrinkHomeSelectEntity(client, coordinator, 101, description)
    state_values, ambiguities = entity._option_state_mapping()
    assert state_values is parameter["option_state_map"]
    assert ambiguities is parameter["ambiguous_option_states"]
    assert state_values == {"off": "2"}
    assert ambiguities == {"relay_1"}


def test_third_value_does_not_reintroduce_an_ambiguous_state() -> None:
    """Keep a conflicting state blocked even if more aliases occur later in the payload."""
    state_values, ambiguities = build_option_state_map(
        (("0", "Relay-1"), ("1", "Relay 1"), ("2", "Relay_1"), ("3", "Off"))
    )
    assert state_values == {"off": "3"}
    assert ambiguities == {"relay_1"}


@pytest.mark.asyncio
async def test_absent_legacy_option_maps_fail_without_writing() -> None:
    """Handle null optional caches as unsupported choices rather than raising attribute errors."""
    client, coordinator = _create_entity_dependencies(
        {
            "valve_control": {
                "value": "1",
                "value_id": 123,
                "options": [],
                "options_map": None,
                "reverse_options_map": None,
            }
        }
    )
    description = next(
        item for item in SELECT_DESCRIPTIONS if item.parameter_key == "valve_control"
    )
    entity = BrinkHomeSelectEntity(client, coordinator, 101, description)
    assert entity.options == []
    assert entity.current_option is None
    with pytest.raises(HomeAssistantError) as raised_error:
        await entity.async_select_option("relay_1")
    assert raised_error.value.translation_key == "unknown_option"
    client.write_parameters.assert_not_awaited()


@pytest.mark.parametrize(
    ("parameter_key", "raw_value", "state_key"),
    (
        ("rh_sensor_sensitivity", "-2", "very_low"),
        ("rh_sensor_sensitivity", "-1", "low"),
        ("signal_output_mode", "0", "off"),
        ("cn1_switch_input_condition", "2", "on_if_bypass_conditions_met"),
    ),
)
@pytest.mark.asyncio
async def test_fixed_option_maps_preserve_raw_values(
    parameter_key: str, raw_value: str, state_key: str
) -> None:
    """Keep fixed mappings, including negative sensitivity values, writable by state key."""
    client, coordinator = _create_entity_dependencies(
        {parameter_key: {"value_id": 123, "value": raw_value}}
    )
    description = next(
        item for item in SELECT_DESCRIPTIONS if item.parameter_key == parameter_key
    )
    entity = BrinkHomeSelectEntity(client, coordinator, 101, description)
    assert entity.current_option == state_key
    assert state_key in entity.options
    await entity.async_select_option(state_key)
    client.write_parameters.assert_awaited_once_with(101, [(123, raw_value)])


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.asyncio
async def test_external_cn1_state_is_translated_and_cannot_be_written(
    language: str,
) -> None:
    """Expose CN1 with a valid translation key and retain its external-control guard."""
    client, coordinator = _create_entity_dependencies(
        {"ventilation_level": {"value_id": 123, "value": "4"}}
    )
    select_description = next(
        item
        for item in SELECT_DESCRIPTIONS
        if item.parameter_key == "ventilation_level"
    )
    sensor_description = next(
        item
        for item in SENSOR_DESCRIPTIONS
        if item.parameter_key == "ventilation_level"
    )
    select_entity = BrinkHomeSelectEntity(client, coordinator, 101, select_description)
    sensor_entity = BrinkHomeSensorEntity(client, coordinator, 101, sensor_description)
    assert select_entity.current_option == sensor_entity.native_value == "cn1"
    assert "cn1" in select_entity.options
    assert "cn1" in sensor_entity.options
    entity_catalog = _load_translations(language)["entity"]
    for entity_domain in ("select", "sensor"):
        assert entity_catalog[entity_domain]["ventilation_level"]["state"]["cn1"]
    with pytest.raises(HomeAssistantError) as raised_error:
        await select_entity.async_select_option("cn1")
    _assert_translatable_error(raised_error.value, language, "external_control")
    client.write_parameters.assert_not_awaited()


def test_dutch_login_and_supply_fan_wording() -> None:
    """Protect Dutch authentication text and the supply versus exhaust distinction."""
    dutch_catalog = _load_translations("nl")
    assert dutch_catalog["config"]["step"]["user"]["data"]["password"] == "Wachtwoord"
    assert (
        dutch_catalog["config"]["abort"]["reauth_successful"]
        == "Opnieuw aanmelden is gelukt."
    )
    assert (
        dutch_catalog["config"]["error"]["invalid_auth"]
        == "E-mailadres of wachtwoord is onjuist."
    )
    for contact_number in (1, 2):
        contact_states = dutch_catalog["entity"]["select"][
            f"contact_{contact_number}_supply_fan_action"
        ]["state"]
        assert (
            contact_states["no_supply_fan_control"] == "Geen regeling toevoerventilator"
        )
        assert (
            contact_states["no_control_supply_fan"] == "Geen regeling toevoerventilator"
        )


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize(
    ("parameter_data", "option", "error_key", "placeholders"),
    (
        (None, "CN1", "external_control", None),
        (None, "Manual", "parameter_unavailable", {"parameter": "operating mode"}),
        (
            {"name": "Mode", "options": []},
            "unsupported",
            "unknown_option",
            {"parameter": "Mode", "option": "unsupported"},
        ),
        (
            {"name": "Mode", "options": [{"value": "1", "label": "Manual"}]},
            "Manual",
            "parameter_unavailable",
            {"parameter": "Mode"},
        ),
    ),
)
@pytest.mark.asyncio
async def test_select_validation_errors_are_translatable(
    language: str,
    parameter_data: dict[str, Any] | None,
    option: str,
    error_key: str,
    placeholders: dict[str, str] | None,
) -> None:
    """Localize select validation failures and reject writes before contacting the API."""
    parameters = {} if parameter_data is None else {"operating_mode": parameter_data}
    client, coordinator = _create_entity_dependencies(parameters)
    description = BrinkSelectEntityDescription(
        key="operating_mode", parameter_key="operating_mode"
    )
    entity = BrinkHomeSelectEntity(client, coordinator, 101, description)
    with pytest.raises(HomeAssistantError) as raised_error:
        await entity.async_select_option(option)
    _assert_translatable_error(raised_error.value, language, error_key, placeholders)
    client.write_parameters.assert_not_awaited()


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("with_parameter", (False, True))
@pytest.mark.asyncio
async def test_number_validation_errors_are_translatable(
    language: str, with_parameter: bool
) -> None:
    """Localize unavailable number parameters and range failures with matching fields."""
    parameters = (
        {"bypass_temperature": {"value_id": 123, "min_value": 10, "max_value": 30}}
        if with_parameter
        else {}
    )
    client, coordinator = _create_entity_dependencies(parameters)
    description = BrinkNumberEntityDescription(
        key="bypass_temperature", parameter_key="bypass_temperature"
    )
    entity = BrinkHomeNumberEntity(client, coordinator, 101, description)
    with pytest.raises(HomeAssistantError) as raised_error:
        await entity.async_set_native_value(40)
    _assert_translatable_error(
        raised_error.value,
        language,
        "value_out_of_range" if with_parameter else "parameter_unavailable",
        {"value": "40", "minimum": "10.0", "maximum": "30.0"}
        if with_parameter
        else {"parameter": "bypass temperature"},
    )
    client.write_parameters.assert_not_awaited()


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize(
    ("method_name", "method_argument", "error_key", "placeholders"),
    (
        ("async_set_level", 5, "invalid_ventilation_level", {"level": "5"}),
        ("async_set_level", 1, "ventilation_parameter_unavailable", None),
        ("async_set_preset_mode", "Manual", "operating_mode_unavailable", None),
        (
            "async_set_preset_mode",
            "unsupported",
            "unknown_preset_mode",
            {"preset_mode": "unsupported"},
        ),
        ("_set_airflow_for_level", 1, "airflow_parameter_unavailable", {"level": "1"}),
        ("_set_airflow_for_level", 1, "device_unavailable", None),
    ),
)
@pytest.mark.asyncio
async def test_fan_validation_errors_are_translatable(
    language: str,
    method_name: str,
    method_argument: int | str,
    error_key: str,
    placeholders: dict[str, str] | None,
) -> None:
    """Cover each fan action failure without writing invalid device parameters."""
    parameters = (
        {"operating_mode": {"value_id": 123, "value": "0"}}
        if error_key == "unknown_preset_mode"
        else {}
    )
    client, coordinator = _create_entity_dependencies(parameters)
    entity = BrinkHomeLevelFanEntity(client, coordinator, 101)
    if error_key == "device_unavailable":
        coordinator.data = {}
    with pytest.raises(HomeAssistantError) as raised_error:
        if method_name == "_set_airflow_for_level":
            await entity._set_airflow_for_level(int(method_argument), 100)
        else:
            await getattr(entity, method_name)(method_argument)
    _assert_translatable_error(raised_error.value, language, error_key, placeholders)
    client.write_parameters.assert_not_awaited()


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.usefixtures("enable_custom_integrations")
@pytest.mark.asyncio
async def test_home_assistant_loads_exception_catalog(
    hass: HomeAssistant, language: str
) -> None:
    """Verify Home Assistant exposes shipped exception messages to the frontend."""
    loaded_catalog = await async_get_translations(
        hass, language, "exceptions", {DOMAIN}
    )
    for error_key, error_data in _load_translations(language)["exceptions"].items():
        assert (
            loaded_catalog[f"component.{DOMAIN}.exceptions.{error_key}.message"]
            == error_data["message"]
        )


@pytest.mark.asyncio
async def test_supported_fan_preset_still_writes_the_raw_value() -> None:
    """Read the parameter payload when setting a preset, then retain its numeric API value."""
    client, coordinator = _create_entity_dependencies(
        {"operating_mode": {"value_id": 123, "value": "0"}}
    )
    entity = BrinkHomeLevelFanEntity(client, coordinator, 101)
    await entity.async_set_preset_mode("Manual")
    client.write_parameters.assert_awaited_once_with(101, [(123, "1")])
    assert entity.preset_mode == "manual"


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.usefixtures("enable_custom_integrations")
@pytest.mark.asyncio
async def test_home_assistant_loads_entity_names_and_runtime_states(
    hass: HomeAssistant, language: str
) -> None:
    """Verify the real translation loader exposes new names and API option aliases."""
    loaded_catalog = await async_get_translations(hass, language, "entity", {DOMAIN})
    entity_catalog = _load_translations(language)["entity"]
    for sensor_key in (
        "owner_group_name",
        "iana_time_zone",
        "two_letter_country_code",
        "active_alert_count",
        "access_level",
    ):
        assert (
            loaded_catalog[f"component.{DOMAIN}.entity.sensor.{sensor_key}.name"]
            == (entity_catalog["sensor"][sensor_key]["name"])
        )
    for parameter_key, _, expected_label in RUNTIME_OPTIONS:
        expected_state = slugify(expected_label)
        assert (
            loaded_catalog[
                f"component.{DOMAIN}.entity.select.{parameter_key}.state.{expected_state}"
            ]
            == entity_catalog["select"][parameter_key]["state"][expected_state]
        )
