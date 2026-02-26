"""Diagnostics support for Brink Home ventilation."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import BrinkConfigEntry

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD, "serial_number", "system_id", "gateway_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: BrinkConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator
    # Replace integer system_id keys with opaque labels to prevent leakage
    devices_redacted = {
        f"device_{i}": async_redact_data(v, TO_REDACT)
        for i, (_, v) in enumerate(sorted((coordinator.data or {}).items()))
    }
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entry_options": dict(entry.options),
        "devices": devices_redacted,
    }
