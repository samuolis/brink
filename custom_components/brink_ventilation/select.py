from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import slugify

from .const import (
    CN_SWITCH_INPUT_CONDITION_LABELS,
    CONTROL_TYPE_MAP,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    FILTER_FAULT_CONDITION_LABELS,
    PARAM_BYPASS_FUNCTION,
    PARAM_BYPASS_OPERATION,
    PARAM_CN1_SWITCH_INPUT_CONDITION,
    PARAM_CN2_SWITCH_INPUT_CONDITION,
    PARAM_CONTACT_1_EXHAUST_FAN_ACTION,
    PARAM_CONTACT_2_EXHAUST_FAN_ACTION,
    PARAM_MODE_VALVE_24V_CONTROL,
    PARAM_OPERATING_MODE,
    PARAM_RH_SENSOR_SENSITIVITY,
    PARAM_SIGNAL_OUTPUT_MODE,
    PARAM_VALVE_CONTROL,
    PARAM_VENTILATION_LEVEL,
    READ_WRITE_MAP,
    RH_SENSOR_SENSITIVITY_LABELS,
    VALUE_STATE_MAP,
)
from .core.option_mapping import build_option_state_map
from .core.parameter_validation import (
    redacted_parameter_attributes,
    writable_value_id,
)
from .entity import BrinkHomeDeviceEntity

if TYPE_CHECKING:
    from .coordinator import BrinkCoordinator
    from .core.brink_home_cloud import BrinkHomeCloud

_LOGGER = logging.getLogger(__name__)

CN1_EXTERNAL_LEVEL = "4"
CN1_EXTERNAL_LABEL = "cn1"


@dataclass(frozen=True, kw_only=True)
class BrinkSelectEntityDescription(SelectEntityDescription):
    """Describe a Brink select entity."""

    parameter_key: str
    label_map: Mapping[str, str] | None = None

    @property
    def reverse_label_map(self) -> dict[str, str]:
        """Return reverse label mapping, cached on the dataclass instance."""
        try:
            return object.__getattribute__(self, "_reverse_label_map_cache")
        except AttributeError:
            reverse = (
                {label: value for value, label in self.label_map.items()}
                if self.label_map
                else {}
            )
            object.__setattr__(self, "_reverse_label_map_cache", reverse)
            return reverse


SELECT_DESCRIPTIONS: tuple[BrinkSelectEntityDescription, ...] = (
    BrinkSelectEntityDescription(
        key="operating_mode",
        translation_key="operating_mode",
        parameter_key=PARAM_OPERATING_MODE,
        icon="mdi:fan-auto",
    ),
    BrinkSelectEntityDescription(
        key="bypass_operation",
        translation_key="bypass_operation",
        parameter_key=PARAM_BYPASS_OPERATION,
        icon="mdi:swap-horizontal",
    ),
    BrinkSelectEntityDescription(
        key="ventilation_level",
        translation_key="ventilation_level",
        parameter_key=PARAM_VENTILATION_LEVEL,
        icon="mdi:fan",
    ),
    BrinkSelectEntityDescription(
        key="bypass_function",
        translation_key="bypass_function",
        parameter_key=PARAM_BYPASS_FUNCTION,
        icon="mdi:tune",
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkSelectEntityDescription(
        key="mode_valve_24v_control",
        translation_key="mode_valve_24v_control",
        parameter_key=PARAM_MODE_VALVE_24V_CONTROL,
        icon="mdi:valve-open",
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkSelectEntityDescription(
        key="valve_control",
        translation_key="valve_control",
        parameter_key=PARAM_VALVE_CONTROL,
        icon="mdi:valve",
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkSelectEntityDescription(
        key="signal_output_mode",
        translation_key="signal_output_mode",
        parameter_key=PARAM_SIGNAL_OUTPUT_MODE,
        label_map=FILTER_FAULT_CONDITION_LABELS,
        icon="mdi:export-variant",
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkSelectEntityDescription(
        key="cn1_conditions",
        translation_key="cn1_conditions",
        parameter_key="cn1_conditions",
        icon="mdi:connection",
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkSelectEntityDescription(
        key="cn2_conditions",
        translation_key="cn2_conditions",
        parameter_key="cn2_conditions",
        icon="mdi:connection",
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkSelectEntityDescription(
        key="mode_input_1",
        translation_key="mode_input_1",
        parameter_key="mode_input_1",
        icon="mdi:import",
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkSelectEntityDescription(
        key="mode_input_2",
        translation_key="mode_input_2",
        parameter_key="mode_input_2",
        icon="mdi:import",
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkSelectEntityDescription(
        key="contact_1_type",
        translation_key="contact_1_type",
        parameter_key="contact_1_type",
        icon="mdi:electric-switch",
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkSelectEntityDescription(
        key="contact_1_supply_fan_action",
        translation_key="contact_1_supply_fan_action",
        parameter_key="contact_1_supply_fan_action",
        icon="mdi:fan",
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkSelectEntityDescription(
        key="contact_1_exhaust_fan_action",
        translation_key="contact_1_exhaust_fan_action",
        parameter_key=PARAM_CONTACT_1_EXHAUST_FAN_ACTION,
        icon="mdi:fan",
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkSelectEntityDescription(
        key="contact_2_type",
        translation_key="contact_2_type",
        parameter_key="contact_2_type",
        icon="mdi:electric-switch",
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkSelectEntityDescription(
        key="contact_2_supply_fan_action",
        translation_key="contact_2_supply_fan_action",
        parameter_key="contact_2_supply_fan_action",
        icon="mdi:fan",
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkSelectEntityDescription(
        key="contact_2_exhaust_fan_action",
        translation_key="contact_2_exhaust_fan_action",
        parameter_key=PARAM_CONTACT_2_EXHAUST_FAN_ACTION,
        icon="mdi:fan",
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkSelectEntityDescription(
        key="supply_fan_control",
        translation_key="supply_fan_control",
        parameter_key="supply_fan_control",
        icon="mdi:fan",
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkSelectEntityDescription(
        key="cn1_switch_input_condition",
        translation_key="cn1_switch_input_condition",
        parameter_key=PARAM_CN1_SWITCH_INPUT_CONDITION,
        label_map=CN_SWITCH_INPUT_CONDITION_LABELS,
        icon="mdi:connection",
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkSelectEntityDescription(
        key="cn2_switch_input_condition",
        translation_key="cn2_switch_input_condition",
        parameter_key=PARAM_CN2_SWITCH_INPUT_CONDITION,
        label_map=CN_SWITCH_INPUT_CONDITION_LABELS,
        icon="mdi:connection",
        entity_category=EntityCategory.CONFIG,
    ),
    BrinkSelectEntityDescription(
        key="rh_sensor_sensitivity",
        translation_key="rh_sensor_sensitivity",
        parameter_key=PARAM_RH_SENSOR_SENSITIVITY,
        label_map=RH_SENSOR_SENSITIVITY_LABELS,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:water-percent",
    )
)


class BrinkHomeSelectEntity(BrinkHomeDeviceEntity, SelectEntity):
    """Base Brink select entity."""

    _attr_has_entity_name = True

    entity_description: BrinkSelectEntityDescription

    def __init__(
        self,
        client: BrinkHomeCloud,
        coordinator: BrinkCoordinator,
        system_id: int,
        description: BrinkSelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(
            client,
            coordinator,
            system_id,
            description.parameter_key,
        )
        self.entity_description = description
        self._fixed_option_states = (
            build_option_state_map(description.label_map.items())
            if description.label_map is not None
            else None
        )

    def _option_state_mapping(self) -> tuple[dict[str, str], set[str]]:
        """Return safe cached states, deriving them for legacy parameter payloads."""
        if self._fixed_option_states is not None:
            return self._fixed_option_states

        parameter = self.data or {}
        cached_states = parameter.get("option_state_map")
        cached_ambiguities = parameter.get("ambiguous_option_states")
        if isinstance(cached_states, dict) and isinstance(cached_ambiguities, set):
            return cached_states, cached_ambiguities

        options = parameter.get("options")
        if options:
            return build_option_state_map(
                (item["value"], item["label"]) for item in options
            )

        options_map = parameter.get("options_map")
        if isinstance(options_map, dict):
            return build_option_state_map(options_map.items())

        reverse_options = parameter.get("reverse_options_map", {})
        if not isinstance(reverse_options, dict):
            return {}, set()
        return build_option_state_map(
            (raw_value, label) for label, raw_value in reverse_options.items()
        )

    async def _async_write_value(self, value: str) -> None:
        """Write a value to the Brink device."""
        param = self.data

        value_id = writable_value_id(param)
        if value_id is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="parameter_unavailable",
                translation_placeholders={"parameter": self.parameter_name},
            )

        await self.client.write_parameters(
            self.system_id,
            [(value_id, value)],
        )

        param["value"] = value

        self.coordinator.async_set_updated_data(
            dict(self.coordinator.data)
        )

        await self.coordinator.async_request_refresh()

    @property
    def icon(self) -> str | None:
        """Return the entity icon."""

        if self.entity_description.key == PARAM_VENTILATION_LEVEL:
            value = str((self.data or {}).get("value", ""))

            return {
                "0": "mdi:fan-off",
                "1": "mdi:fan-speed-1",
                "2": "mdi:fan-speed-2",
                "3": "mdi:fan-speed-3",
                "4": "mdi:connection"
            }.get(value, "mdi:fan")

        return self.entity_description.icon

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return extra state attributes."""
        param = self.data or {}

        # Get base attributes
        attributes: dict[str, object] = {}

        # These attibutes are available to select entity
        attributes |= {
            "key": self.entity_description.key,
            "translation_key": self.entity_description.translation_key,
            "name": param.get("name", "unavailable"),
            "raw_name": param.get("raw_name", "unavailable"),
            "value": param.get("value", "unavailable"),
            "numeric_id": param.get("numeric_id", "unavailable"),
            "value_id": param.get("value_id", "onbeschikbaar"),
            "component_id": param.get("component_id", "unavailable"),
            "raw_options": param.get("options", "unavailable"),
        }

        value_state = param.get("value_state")
        attributes["raw_value_state"] = value_state

        if isinstance(value_state, int):
            attributes["value_state"] = VALUE_STATE_MAP.get(value_state, "unknown")
        else:
            attributes["value_state"] = "unavailable"

        control_type = param.get("control_type")
        attributes["raw_control_type"] = control_type

        if isinstance(control_type, int):
            attributes["control_type"] = CONTROL_TYPE_MAP.get(control_type, "unknown")
        else:
            attributes["control_type"] = "unavailable"

        read_write = param.get("read_write")
        attributes["raw_read_write"] = read_write

        if isinstance(read_write, int):
            attributes["read_write"] = READ_WRITE_MAP.get(read_write, "unknown")
        else:
            attributes["read_write"] = "unavailable"

        # These attibutes are NOT available to select entity, if they do it should not be a select entity
        for key in (
            "default_value",
            "raw_value",
            "unit_of_measure",
            "min_value",
            "max_value",
            "step_width",
            "decimals",
        ):
            if (value := param.get(key)) is not None:
                attributes[key] = value
            # else:
            #    attributes[key] = "unavailable"

        return redacted_parameter_attributes(attributes)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return (
            f"{DOMAIN}_{self.system_id}_"
            f"{self.parameter_key}_select"
        )

    async def async_select_option(
        self,
        option: str,
    ) -> None:
        """Select an option."""
        if option in {"CN1", CN1_EXTERNAL_LABEL}:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="external_control",
            )

        param = self.data

        if param is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="parameter_unavailable",
                translation_placeholders={"parameter": self.parameter_name},
            )

        state_values, ambiguous_states = self._option_state_mapping()
        option_state = slugify(option)
        if option_state in ambiguous_states:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="ambiguous_option",
                translation_placeholders={
                    "option": option,
                    "parameter": self.parameter_name,
                },
            )

        selected_value = state_values.get(option_state)

        if selected_value is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_option",
                translation_placeholders={
                    "option": option,
                    "parameter": self.parameter_name,
                },
            )

        await self._async_write_value(str(selected_value))

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        param = self.data

        if param is None:
            return None

        current_value = str(param.get("value"))

        if (
            self.entity_description.parameter_key == PARAM_VENTILATION_LEVEL
            and current_value == CN1_EXTERNAL_LEVEL
        ):
            return CN1_EXTERNAL_LABEL

        if (label_map := self.entity_description.label_map) is not None:
            selected_label = label_map.get(current_value)

        elif (options_map := param.get("options_map")) is not None:
            selected_label = options_map.get(current_value)
        else:
            selected_label = next(
                (
                    option["label"]
                    for option in param.get("options", [])
                    if option["value"] == current_value
                ),
                None,
            )

        if selected_label is None:
            return None

        state_key = slugify(selected_label)
        state_values, _ = self._option_state_mapping()
        return state_key if state_values.get(state_key) == current_value else None

    @property
    def options(self) -> list[str]:
        """Return available options."""

        state_values, _ = self._option_state_mapping()
        options = list(state_values)

        if (
            self.entity_description.parameter_key == PARAM_VENTILATION_LEVEL
            and self.current_option == CN1_EXTERNAL_LABEL
            and CN1_EXTERNAL_LABEL not in options
        ):
            options.append(CN1_EXTERNAL_LABEL)

        return options

    @property
    def available(self) -> bool:
        """Return if entity is available."""

        if not super().available:
            return False

        # Use O(1) device lookup by system_id instead of creating temporary dict_values views/iterators
        device = self._device
        if device is None:
            return False

        parameters = device.parameters

        # _LOGGER.debug(
        #    "gateway_state available: super=%s data=%s current_value=%s",
        #    super().available,
        #    self.data,
        #    self.current_option,
        # )

        if self.entity_description.parameter_key == "rh_sensor_sensitivity":
            rh_sensor_value = parameters.get("ebus_co2_sensor_status", {}).get("value")

            try:
                rh_sensor = int(rh_sensor_value)
            except (TypeError, ValueError):
                return False

            return rh_sensor == 1

        param = self.data

        return (
            param is not None
            and param.get("value_state") != 5
        )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Brink select platform."""
    client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities = [
        BrinkHomeSelectEntity(
            client,
            coordinator,
            system_id,
            description,
        )
        for system_id, device in (coordinator.data or {}).items()
        for description in SELECT_DESCRIPTIONS
        if device.parameters.get(description.parameter_key) is not None
    ]

    async_add_entities(entities)
