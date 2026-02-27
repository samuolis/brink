"""Diagnostics support for Brink Home ventilation."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import BrinkConfigEntry
from .const import (
    CONF_HUMIDITY_SENSOR_1,
    CONF_HUMIDITY_SENSOR_2,
    CONF_HUMIDITY_SENSOR_3,
    CONF_TEMPERATURE_SOURCE_ENTITY,
)

TO_REDACT = {
    CONF_USERNAME, CONF_PASSWORD, "serial_number", "system_id", "gateway_id",
    CONF_HUMIDITY_SENSOR_1, CONF_HUMIDITY_SENSOR_2, CONF_HUMIDITY_SENSOR_3,
    CONF_TEMPERATURE_SOURCE_ENTITY,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: BrinkConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator
    controller = coordinator.automation_controller
    controller_diagnostics = {
        "state": str(controller.state),
        "season": controller.season,
        "boost_remaining_minutes": controller.boost_remaining_minutes,
        "has_pending_writes": controller.has_pending_writes,
        "humidity_sensors_configured": len(controller.configured_humidity_sensors),
    }
    # Replace integer system_id keys with opaque labels to prevent leakage
    devices_redacted = {
        f"device_{i}": async_redact_data(v, TO_REDACT)
        for i, (_, v) in enumerate(sorted((coordinator.data or {}).items()))
    }
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entry_options": async_redact_data(dict(entry.options), TO_REDACT),
        "devices": devices_redacted,
        "automation_controller": controller_diagnostics,
    }
