from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant

from .const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    GATEWAY_STATE_LABELS,
    GATEWAY_STATE_ONLINE,
    PARAM_CN1_POSITION,
    PARAM_CN1_SWITCH_INPUT,
    PARAM_CN2_POSITION,
    PARAM_CN2_SWITCH_INPUT,
    PARAM_FILTER_STATUS,
    PARAM_RH_SENSOR_STATUS,
)
from .core.parameter_validation import redacted_parameter_attributes
from .entity import BrinkHomeDeviceEntity
from .models import BrinkAlertLevel

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class BrinkBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a Brink binary sensor."""

    parameter_key: str
    requires_parameter: bool = True

    value_fn: Callable[
        [BrinkHomeBinarySensorEntity],
        bool | None,
    ] | None = None

    attr_fn: Callable[
        [BrinkHomeBinarySensorEntity],
        dict[str, object],
    ] | None = None

    icon_fn: Callable[
        [BrinkHomeBinarySensorEntity],
        str | None,
    ] | None = None

    available_fn: Callable[
        [BrinkHomeBinarySensorEntity],
        bool,
    ] | None = None


class BrinkHomeBinarySensorEntity(
    BrinkHomeDeviceEntity,
    BinarySensorEntity,
):
    """Representation of a Brink binary sensor."""

    _attr_has_entity_name = True

    entity_description: BrinkBinarySensorDescription

    def __init__(
        self,
        client,
        coordinator,
        system_id: int,
        description: BrinkBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(
            client,
            coordinator,
            system_id,
            description.parameter_key,
        )
        self.entity_description = description

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        key = self.entity_description.key
        if key == "gateway_status":
            return f"{DOMAIN}_{self.system_id}_online"
        if key == PARAM_FILTER_STATUS:
            return f"{DOMAIN}_{self.system_id}_{self.parameter_key}_binary_sensor"
        return f"{DOMAIN}_{self.system_id}_{key}

    @property
    def icon(self) -> str | None:
        """Return the entity icon."""
        icon_fn = self.entity_description.icon_fn

        if icon_fn is not None:
            return icon_fn(self)

        return self.entity_description.icon

    @property
    def is_on(self) -> bool | None:
        """Return sensor state."""

        value_fn = self.entity_description.value_fn

        if value_fn is not None:
            return value_fn(self)

        data = self.data

        if data is None:
            return None

        value = data.get("value")

        if value is None:
            return None

        return str(value) == "1"

    @property
    def available(self) -> bool:
        """Return if entity is available."""

        available_fn = self.entity_description.available_fn
        if available_fn is not None:
            return bool(available_fn(self))

        if not self.entity_description.requires_parameter:
            return True

        if not super().available:
            return False

        data = self.data

        return (
            data is not None
            and data.get("value_state") != 5
        )

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return extra state attributes."""
        attributes: dict[str, object] = {
            "key": _debug_value(self.entity_description.key),
            "translation_key": _debug_value(
                self.entity_description.translation_key,
            ),
        }

        data = self.data
        if data is not None:
            attributes.update(
                {
                    "name": _debug_value(data.get("name")),
                    "raw_name": _debug_value(data.get("raw_name")),
                    "value": _debug_value(data.get("value")),
                    "value_state": _debug_value(data.get("value_state")),
                    "default_value": _debug_value(data.get("default_value")),
                    "numeric_id": _debug_value(data.get("numeric_id")),
                    "read_write": _debug_value(data.get("read_write")),
                    "control_type": _debug_value(data.get("control_type")),
                    "value_id": _debug_value(data.get("value_id")),
                    "list_items": _debug_value(data.get("list_items")),
                    "component_id": _debug_value(data.get("component_id")),
                    "options": data.get("options"),
                    "options_str": _debug_value(data.get("options")),
                }
            )

            # Binary sensors should not expose these. If present they
            # probably belong to a Number or Select entity.
            for key in (
                "min_value",
                "max_value",
                "step_width",
                "decimals",
                "unit_of_measure",
            ):
                if data.get(key) is not None:
                    attributes[key] = data[key]

        attr_fn = self.entity_description.attr_fn
        if attr_fn is not None:
            custom_attributes = attr_fn(self)
            if custom_attributes:
                attributes.update(custom_attributes)

        return redacted_parameter_attributes(attributes)

    @property
    def gateway_state(self) -> int | None:
        """Return the gateway state."""
        device = self._device
        return None if device is None else _normalize_gateway_state(device.gateway_state)

    @property
    def device_is_online(self) -> bool | None:
        """Return whether the device is online."""
        device = self._device

        return None if device is None else device.device_is_online

    @property
    def gateway_type_id(self) -> int | None:
        """Return the gateway type ID."""
        device = self._device

        return None if device is None else device.gateway_type_id


def _debug_value(value: object) -> str:
    """Convert a diagnostic value to a string."""
    return str(value)


def _normalize_gateway_state(value: object) -> int | None:
    """Accept known numeric/string states without guessing an online state."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value in GATEWAY_STATE_LABELS:
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        for identifier, label in GATEWAY_STATE_LABELS.items():
            if normalized in (str(identifier), label):
                return identifier
    return None


def _get_blocking_error_attributes(entity: BrinkHomeBinarySensorEntity) -> dict[str, object]:
    """Return extra state attributes for the blocking error binary sensor."""
    active_alerts = entity.coordinator.active_alerts
    if not active_alerts:
        return {
            "alert_count": 0,
            "highest_level": BrinkAlertLevel.INFORMATION.name,
            "highest_level_value": int(BrinkAlertLevel.INFORMATION),
            "alerts": [],
        }

    # Evaluate highest alert level in a single O(N) pass
    highest_alert = max(active_alerts, key=lambda alert: alert.level)
    return {
        "alert_count": len(active_alerts),
        "highest_level": highest_alert.level.name,
        "highest_level_value": int(highest_alert.level),
        "alerts": [
            {
                "id": alert.id,
                "component_id": alert.component_id,
                "code": alert.code,
                "level": alert.level.name,
                "level_value": int(alert.level),
                "is_active": alert.is_active,
                "is_archived": alert.is_archived,
                "incoming": alert.incoming.isoformat(),
                "outgoing": (
                    alert.outgoing.isoformat()
                    if alert.outgoing is not None
                    else None
                ),
                "code_text": alert.code_text,
                "description": alert.description,
            }
            for alert in active_alerts
        ],
    }


BINARY_SENSOR_DESCRIPTIONS: tuple[BrinkBinarySensorDescription, ...] = (
    BrinkBinarySensorDescription(
        key="gateway_status",
        translation_key="gateway_status",
        parameter_key="gateway_status",
        requires_parameter=False,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda entity: (
            None
            if entity.gateway_state is None
            else entity.gateway_state == GATEWAY_STATE_ONLINE
        ),
        attr_fn=lambda entity: {
            "gateway_state": entity.gateway_state,
            "device_is_online": entity.device_is_online,
            "gateway_type_id": entity.gateway_type_id,
            "gateway_state_label": GATEWAY_STATE_LABELS.get(
                entity.gateway_state,
                "unknown",
            ),
        },
        available_fn=lambda entity: entity.coordinator.last_update_success,
        icon_fn=lambda entity: (
            "mdi:connection"
            if entity.is_on
            else "mdi:lan-disconnect"
        ),
    ),
    BrinkBinarySensorDescription(
        key="device_online",
        translation_key="device_online",
        parameter_key="device_online",
        requires_parameter=False,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda entity: entity.device_is_online,
        available_fn=lambda entity: entity.coordinator.last_update_success,
        icon_fn=lambda entity: (
            "mdi:connection"
            if entity.is_on
            else "mdi:lan-disconnect"
        ),
    ),
    BrinkBinarySensorDescription(
        key=PARAM_FILTER_STATUS,
        translation_key="status_filter_message",
        parameter_key=PARAM_FILTER_STATUS,
        icon="mdi:air-filter",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda entity: entity.parameter_value == "1"
    ),
    BrinkBinarySensorDescription(
        key=PARAM_RH_SENSOR_STATUS,
        translation_key="rh_sensor_status",
        parameter_key=PARAM_RH_SENSOR_STATUS,
        icon="mdi:water-percent",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_registry_enabled_default=False,
    ),
    BrinkBinarySensorDescription(
        key="ebus_co2_sensor_status",
        translation_key="ebus_co2_sensor_status",
        parameter_key="ebus_co2_sensor_status",
        icon="mdi:molecule-co2",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        available_fn=lambda data: True,
        entity_registry_enabled_default=False,
    ),
    BrinkBinarySensorDescription(
        key="cn1_position",
        translation_key="cn1_position",
        parameter_key=PARAM_CN1_POSITION,
        icon="mdi:electric-switch",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkBinarySensorDescription(
        key="cn2_position",
        translation_key="cn2_position",
        parameter_key=PARAM_CN2_POSITION,
        icon="mdi:electric-switch",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrinkBinarySensorDescription(
        key="cn1_switch_input",
        translation_key="cn1_switch_input",
        parameter_key=PARAM_CN1_SWITCH_INPUT,
        icon="mdi:electric-switch",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    BrinkBinarySensorDescription(
        key="cn2_switch_input",
        translation_key="cn2_switch_input",
        parameter_key=PARAM_CN2_SWITCH_INPUT,
        icon="mdi:electric-switch",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    BrinkBinarySensorDescription(
        key="blocking_error",
        translation_key="blocking_error",
        parameter_key="blocking_error",
        requires_parameter=False,
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:alert-octagon",
        value_fn=lambda entity: entity.coordinator.has_blocking_error,
        attr_fn=_get_blocking_error_attributes,
    ),
    BrinkBinarySensorDescription(
        key="api_online",
        translation_key="api_online",
        parameter_key="api_online",
        requires_parameter=False,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda entity: entity.api_is_online,
        attr_fn=lambda entity: (
            {
                "api_error": entity.api_error,
                "api_error_code": entity.api_error_code,
                "api_error_type": entity.api_error_type,
            }
            if not entity.api_is_online
            else {}
        ),
        available_fn=lambda entity: True,
        icon_fn=lambda entity: (
            "mdi:cloud-check"
            if entity.is_on
            else "mdi:cloud-off-outline"
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
    )
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up Brink binary sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    entities = []

    for system_id, device in (coordinator.data or {}).items():
        for description in BINARY_SENSOR_DESCRIPTIONS:
            if (
                not description.requires_parameter
                or device.parameters.get(description.parameter_key) is not None
            ):
                entities.append(
                    BrinkHomeBinarySensorEntity(
                        client,
                        coordinator,
                        system_id,
                        description,
                    )
                )

    async_add_entities(entities)
