"""Logbook event descriptions for Brink Home Ventilation."""

from __future__ import annotations

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from homeassistant.core import Event, HomeAssistant, callback

from .const import (
    BOOST_TRIGGER_HUMIDITY,
    DOMAIN,
    EVENT_BOOST_ACTIVATED,
    EVENT_BOOST_DEACTIVATED,
)


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event,
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_boost_activated(event: Event) -> dict[str, str]:
        """Describe boost activated event."""
        data = event.data
        trigger = data.get("trigger")
        duration = data.get("duration", "?")
        level = data.get("level", "?")

        if trigger == BOOST_TRIGGER_HUMIDITY:
            sensor = data.get("sensor", "unknown sensor")
            rate = data.get("rate")
            rate_str = f" ({rate}%/min)" if rate is not None else ""
            message = (
                f"activated due to humidity spike on {sensor}{rate_str}"
                f" (level {level}, {duration} min)"
            )
        else:
            message = f"activated manually (level {level}, {duration} min)"

        return {
            LOGBOOK_ENTRY_NAME: "Extra ventilation",
            LOGBOOK_ENTRY_MESSAGE: message,
        }

    @callback
    def async_describe_boost_deactivated(event: Event) -> dict[str, str]:
        """Describe boost deactivated event."""
        data = event.data
        reason = data.get("reason", "unknown")

        if reason == "timer_expired":
            message = "deactivated (timer expired)"
        elif reason == "cancelled":
            message = "deactivated (cancelled manually)"
        else:
            message = f"deactivated ({reason})"

        return {
            LOGBOOK_ENTRY_NAME: "Extra ventilation",
            LOGBOOK_ENTRY_MESSAGE: message,
        }

    async_describe_event(DOMAIN, EVENT_BOOST_ACTIVATED, async_describe_boost_activated)
    async_describe_event(
        DOMAIN, EVENT_BOOST_DEACTIVATED, async_describe_boost_deactivated
    )
