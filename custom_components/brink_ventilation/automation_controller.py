"""Automation controller for Brink Home ventilation.

Implements a 3-state state machine (IDLE / BASE / BOOSTED) that manages
seasonal ventilation levels, humidity-spike detection, and a resilient
write queue that retries failed API writes on the next coordinator refresh.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
)

from .const import (
    CONF_AUTO_SUMMER_BASE_LEVEL,
    CONF_AUTO_WINTER_BASE_LEVEL,
    CONF_EXTRA_VENT_DURATION,
    CONF_EXTRA_VENT_SUMMER_LEVEL,
    CONF_EXTRA_VENT_WINTER_LEVEL,
    CONF_FREEZING_THRESHOLD,
    CONF_HUMIDITY_SENSOR_1,
    CONF_HUMIDITY_SENSOR_2,
    CONF_HUMIDITY_SENSOR_3,
    CONF_HUMIDITY_SPIKE_THRESHOLD,
    CONF_TEMPERATURE_SOURCE_ENTITY,
    DEFAULT_AUTO_SUMMER_BASE_LEVEL,
    DEFAULT_AUTO_WINTER_BASE_LEVEL,
    DEFAULT_EXTRA_VENT_DURATION,
    DEFAULT_EXTRA_VENT_SUMMER_LEVEL,
    DEFAULT_EXTRA_VENT_WINTER_LEVEL,
    DEFAULT_FREEZING_THRESHOLD,
    DEFAULT_HUMIDITY_SPIKE_THRESHOLD,
    HUMIDITY_MIN_SAMPLE_INTERVAL,
    HUMIDITY_WINDOW_SECONDS,
    PARAM_FRESH_AIR_TEMP,
    PARAM_OPERATING_MODE,
    PARAM_VENTILATION_LEVEL,
    SEASON_SUMMER,
    SEASON_WINTER,
)

if TYPE_CHECKING:
    from .coordinator import BrinkDataCoordinator

_LOGGER = logging.getLogger(__name__)

_COUNTDOWN_INTERVAL = 30  # seconds between countdown updates


class AutomationState(StrEnum):
    """State machine states for the Brink automation controller."""

    IDLE = "idle"
    BASE = "base"
    BOOSTED = "boosted"


class BrinkAutomationController:
    """Manages seasonal ventilation, humidity-spike boost, and write retries.

    State machine:
        IDLE  --(ha_automated selected)-->  BASE
        BASE  --(humidity spike / button)-->  BOOSTED
        BOOSTED  --(timer expires)-->  BASE
        BASE / BOOSTED  --(ha_automated deselected)-->  IDLE
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: BrinkDataCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the automation controller."""
        self._hass = hass
        self._coordinator = coordinator
        self._entry = entry

        self._state: AutomationState = AutomationState.IDLE
        self._season: str | None = None

        # Humidity rolling windows: entity_id -> deque of (timestamp, value)
        self._humidity_windows: dict[str, deque[tuple[float, float]]] = {}

        # Resilient write queue -- stores the most recent desired params on failure
        self._pending_writes: list[tuple[int, str]] | None = None

        # Track whether automation was in BASE before boost (for correct return state)
        self._was_in_base_before_boost: bool = False

        # Unsub handles
        self._boost_timer_unsub: CALLBACK_TYPE | None = None
        self._countdown_timer_unsub: CALLBACK_TYPE | None = None
        self._humidity_listener_unsub: CALLBACK_TYPE | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> AutomationState:
        """Return the current automation state."""
        return self._state

    @property
    def season(self) -> str | None:
        """Return the current season (SEASON_SUMMER or SEASON_WINTER)."""
        return self._season

    @property
    def boost_remaining_minutes(self) -> int:
        """Return remaining boost minutes, 0 when not boosted."""
        if self._state != AutomationState.BOOSTED:
            return 0
        if not hasattr(self, "_boost_end_monotonic"):
            return 0
        remaining = self._boost_end_monotonic - time.monotonic()
        if remaining <= 0:
            return 0
        return int(remaining / 60) + (1 if remaining % 60 > 0 else 0)

    @property
    def has_pending_writes(self) -> bool:
        """Return True if there are pending writes awaiting retry."""
        return self._pending_writes is not None

    @property
    def configured_humidity_sensors(self) -> list[str]:
        """Return entity_ids of configured humidity sensors from options."""
        options = self._entry.options
        sensors: list[str] = []
        for key in (CONF_HUMIDITY_SENSOR_1, CONF_HUMIDITY_SENSOR_2, CONF_HUMIDITY_SENSOR_3):
            entity_id = options.get(key, "")
            if entity_id:
                sensors.append(entity_id)
        return sensors

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def async_activate(self) -> None:
        """Transition IDLE -> BASE: start seasonal ventilation and humidity monitoring."""
        if self._state != AutomationState.IDLE:
            _LOGGER.debug(
                "async_activate called in state %s, expected IDLE", self._state
            )
            return

        self._season = self._evaluate_season()
        self._state = AutomationState.BASE

        self._start_humidity_listeners()

        base_level = self._get_seasonal_base_level()
        params = self._build_mode_and_level_params(mode_value="1", level_value=str(base_level))
        if params:
            await self.async_write_params(params)

        _LOGGER.info(
            "Automation activated: season=%s, base_level=%s",
            self._season,
            base_level,
        )

    async def async_deactivate(self) -> None:
        """Transition any state -> IDLE: cancel all timers and listeners."""
        _LOGGER.info("Automation deactivating from state %s", self._state)

        self._cancel_boost_timer()
        self._cancel_countdown_timer()
        self._remove_humidity_listeners()
        self._humidity_windows.clear()
        self._pending_writes = None
        self._was_in_base_before_boost = False
        self._state = AutomationState.IDLE

    async def async_activate_extra_ventilation(self) -> None:
        """Activate extra ventilation boost (shared by button and humidity trigger).

        Sets the device to the seasonal max level in manual mode and starts
        the boost timer.
        """
        self._was_in_base_before_boost = self._state == AutomationState.BASE

        self._season = self._evaluate_season()
        max_level = self._get_seasonal_max_level()
        duration_minutes: int = int(
            self._entry.options.get(CONF_EXTRA_VENT_DURATION, DEFAULT_EXTRA_VENT_DURATION)
        )

        params = self._build_mode_and_level_params(mode_value="1", level_value=str(max_level))
        if params:
            await self.async_write_params(params)

        # Cancel existing boost timer before starting a new one
        self._cancel_boost_timer()
        self._cancel_countdown_timer()

        self._boost_end_monotonic = time.monotonic() + duration_minutes * 60

        self._boost_timer_unsub = async_call_later(
            self._hass,
            duration_minutes * 60,
            self._async_boost_timer_expired,
        )

        self._start_countdown_timer()
        self._state = AutomationState.BOOSTED

        _LOGGER.info(
            "Extra ventilation activated: season=%s, max_level=%s, duration=%d min",
            self._season,
            max_level,
            duration_minutes,
        )

    async def async_on_coordinator_update(self) -> None:
        """Handle coordinator data refresh: re-evaluate season and retry writes."""
        if self._state == AutomationState.IDLE:
            return

        old_season = self._season
        self._season = self._evaluate_season()

        if old_season != self._season and self._season is not None:
            _LOGGER.info("Season changed: %s -> %s", old_season, self._season)
            if self._state == AutomationState.BASE:
                base_level = self._get_seasonal_base_level()
                params = self._build_mode_and_level_params(
                    mode_value="1", level_value=str(base_level)
                )
                if params:
                    await self.async_write_params(params)
            elif self._state == AutomationState.BOOSTED:
                max_level = self._get_seasonal_max_level()
                params = self._build_mode_and_level_params(
                    mode_value="1", level_value=str(max_level)
                )
                if params:
                    await self.async_write_params(params)

        await self._async_retry_pending_writes()

    async def async_restore_state(self) -> None:
        """Restore automation state after HA restart.

        Checks entry.options for a stored ha_automated_active flag. If the
        automation was active before HA restarted, re-activate it.
        """
        if self._entry.options.get("ha_automated_active", False):
            _LOGGER.info("Restoring ha_automated state after restart")
            # Reset state to IDLE so async_activate can transition properly
            self._state = AutomationState.IDLE
            await self.async_activate()

    async def async_options_updated(self) -> None:
        """Handle options flow update: re-subscribe listeners and re-evaluate season."""
        if self._state == AutomationState.IDLE:
            return

        # Re-subscribe humidity listeners (sensors may have changed)
        self._remove_humidity_listeners()
        self._humidity_windows.clear()
        self._start_humidity_listeners()

        # Re-evaluate season with potentially new threshold
        old_season = self._season
        self._season = self._evaluate_season()

        if old_season != self._season and self._season is not None:
            _LOGGER.info(
                "Season changed after options update: %s -> %s",
                old_season,
                self._season,
            )
            if self._state == AutomationState.BASE:
                base_level = self._get_seasonal_base_level()
                params = self._build_mode_and_level_params(
                    mode_value="1", level_value=str(base_level)
                )
                if params:
                    await self.async_write_params(params)
            elif self._state == AutomationState.BOOSTED:
                max_level = self._get_seasonal_max_level()
                params = self._build_mode_and_level_params(
                    mode_value="1", level_value=str(max_level)
                )
                if params:
                    await self.async_write_params(params)

    async def async_cleanup(self) -> None:
        """Cancel all timers and listeners, clear state."""
        self._cancel_boost_timer()
        self._cancel_countdown_timer()
        self._remove_humidity_listeners()
        self._humidity_windows.clear()
        self._pending_writes = None
        self._state = AutomationState.IDLE
        self._season = None

    # ------------------------------------------------------------------
    # Write queue
    # ------------------------------------------------------------------

    async def async_write_params(self, params: list[tuple[int, str]]) -> None:
        """Write parameters to the API with retry-on-failure semantics.

        On success: clears pending_writes, starts expedited polling.
        On failure: stores params as pending_writes for retry on next refresh.
        """
        system_id, gateway_id = self._get_system_and_gateway_ids()
        if system_id is None or gateway_id is None:
            _LOGGER.warning("Cannot write: system_id or gateway_id unavailable")
            self._pending_writes = params
            return

        try:
            await self._coordinator.client.write_parameters(
                system_id, gateway_id, params
            )
        except Exception:
            _LOGGER.warning(
                "Write failed, queuing for retry: %s",
                params,
                exc_info=True,
            )
            self._pending_writes = params
            return

        self._pending_writes = None
        self._coordinator.start_expedited_polling()
        _LOGGER.debug("Write succeeded: %s", params)

    async def _async_retry_pending_writes(self) -> None:
        """Retry pending writes if any exist."""
        if self._pending_writes is not None:
            _LOGGER.debug("Retrying pending writes: %s", self._pending_writes)
            await self.async_write_params(self._pending_writes)

    # ------------------------------------------------------------------
    # Boost timer callbacks
    # ------------------------------------------------------------------

    @callback
    def _async_boost_timer_expired(self, _now: Any) -> None:
        """Handle boost timer expiration."""
        self._boost_timer_unsub = None
        self._cancel_countdown_timer()

        if self._state == AutomationState.BOOSTED:
            if self._was_in_base_before_boost:
                _LOGGER.info("Boost timer expired, transitioning to BASE")
                self._state = AutomationState.BASE
                self._season = self._evaluate_season()

                base_level = self._get_seasonal_base_level()
                params = self._build_mode_and_level_params(
                    mode_value="1", level_value=str(base_level)
                )
                if params:
                    self._hass.async_create_task(self.async_write_params(params))

                # Resume humidity monitoring (was paused during boost)
                self._start_humidity_listeners()
            else:
                _LOGGER.info(
                    "Boost timer expired, transitioning to IDLE "
                    "(boost was triggered outside ha_automated mode)"
                )
                self._state = AutomationState.IDLE
        else:
            _LOGGER.debug("Boost timer expired but state is %s", self._state)

    # ------------------------------------------------------------------
    # Countdown timer (forces entity updates for remaining-time display)
    # ------------------------------------------------------------------

    def _start_countdown_timer(self) -> None:
        """Start a periodic 30-second countdown timer to refresh entity states."""
        self._cancel_countdown_timer()

        @callback
        def _countdown_tick(_now: Any) -> None:
            """Trigger an entity state update and reschedule."""
            if self._state != AutomationState.BOOSTED:
                self._countdown_timer_unsub = None
                return

            # Force entity state update by re-setting coordinator data
            self._coordinator.async_set_updated_data(self._coordinator.data)

            # Reschedule
            self._countdown_timer_unsub = async_call_later(
                self._hass, _COUNTDOWN_INTERVAL, _countdown_tick
            )

        self._countdown_timer_unsub = async_call_later(
            self._hass, _COUNTDOWN_INTERVAL, _countdown_tick
        )

    def _cancel_countdown_timer(self) -> None:
        """Cancel the countdown update timer if active."""
        if self._countdown_timer_unsub is not None:
            self._countdown_timer_unsub()
            self._countdown_timer_unsub = None

    # ------------------------------------------------------------------
    # Humidity monitoring
    # ------------------------------------------------------------------

    def _start_humidity_listeners(self) -> None:
        """Subscribe to state changes for configured humidity sensors."""
        self._remove_humidity_listeners()
        sensors = self.configured_humidity_sensors
        if not sensors:
            _LOGGER.debug("No humidity sensors configured, skipping listeners")
            return

        self._humidity_listener_unsub = async_track_state_change_event(
            self._hass, sensors, self._async_humidity_state_changed
        )
        _LOGGER.debug("Started humidity listeners for: %s", sensors)

    def _remove_humidity_listeners(self) -> None:
        """Remove humidity sensor state-change listeners."""
        if self._humidity_listener_unsub is not None:
            self._humidity_listener_unsub()
            self._humidity_listener_unsub = None

    @callback
    def _async_humidity_state_changed(self, event: Event) -> None:
        """Handle humidity sensor state changes for spike detection."""
        if self._state != AutomationState.BASE:
            return

        entity_id: str = event.data.get("entity_id", "")
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        state_value = new_state.state
        if state_value in (None, "unavailable", "unknown"):
            return

        try:
            value = float(state_value)
        except (ValueError, TypeError):
            return

        now = time.monotonic()

        # Get or create rolling window for this sensor
        if entity_id not in self._humidity_windows:
            self._humidity_windows[entity_id] = deque()
        window = self._humidity_windows[entity_id]

        # Enforce minimum sample interval
        if window and (now - window[-1][0]) < HUMIDITY_MIN_SAMPLE_INTERVAL:
            return

        window.append((now, value))

        # Trim entries older than HUMIDITY_WINDOW_SECONDS
        cutoff = now - HUMIDITY_WINDOW_SECONDS
        while window and window[0][0] < cutoff:
            window.popleft()

        # Spike detection
        if len(window) >= 2:
            threshold: float = float(
                self._entry.options.get(
                    CONF_HUMIDITY_SPIKE_THRESHOLD, DEFAULT_HUMIDITY_SPIKE_THRESHOLD
                )
            )
            oldest_value = window[0][1]
            newest_value = window[-1][1]

            if (newest_value - oldest_value) >= threshold:
                _LOGGER.info(
                    "Humidity spike detected on %s: %.1f -> %.1f (threshold %.1f)",
                    entity_id,
                    oldest_value,
                    newest_value,
                    threshold,
                )
                # Clear window to prevent re-triggering immediately
                window.clear()
                self._hass.async_create_task(
                    self.async_activate_extra_ventilation()
                )

    # ------------------------------------------------------------------
    # Season evaluation
    # ------------------------------------------------------------------

    def _get_current_temperature(self) -> float | None:
        """Get the current temperature from configured source or coordinator data."""
        # Check for user-configured temperature source entity
        temp_entity_id: str = self._entry.options.get(
            CONF_TEMPERATURE_SOURCE_ENTITY, ""
        )
        if temp_entity_id:
            state = self._hass.states.get(temp_entity_id)
            if state is not None and state.state not in (
                None,
                "unavailable",
                "unknown",
            ):
                try:
                    return float(state.state)
                except (ValueError, TypeError):
                    pass

        # Fall back to PARAM_FRESH_AIR_TEMP from coordinator data
        data = self._coordinator.data
        if not data:
            return None

        for device in data.values():
            for component in device.get("components", []):
                param = component.get("parameters", {}).get(PARAM_FRESH_AIR_TEMP)
                if param is not None:
                    raw = param.get("value")
                    if raw is not None:
                        try:
                            return float(raw)
                        except (ValueError, TypeError):
                            pass

        return None

    def _evaluate_season(self) -> str | None:
        """Determine the current season based on temperature.

        Returns the current season unchanged if temperature is unavailable.
        """
        temperature = self._get_current_temperature()
        if temperature is None:
            return self._season

        threshold: float = float(
            self._entry.options.get(
                CONF_FREEZING_THRESHOLD, DEFAULT_FREEZING_THRESHOLD
            )
        )

        if temperature >= threshold:
            return SEASON_SUMMER
        return SEASON_WINTER

    # ------------------------------------------------------------------
    # Seasonal level helpers
    # ------------------------------------------------------------------

    def _get_seasonal_base_level(self) -> int:
        """Return the configured base ventilation level for the current season."""
        options = self._entry.options
        if self._season == SEASON_WINTER:
            return int(options.get(CONF_AUTO_WINTER_BASE_LEVEL, DEFAULT_AUTO_WINTER_BASE_LEVEL))
        return int(options.get(CONF_AUTO_SUMMER_BASE_LEVEL, DEFAULT_AUTO_SUMMER_BASE_LEVEL))

    def _get_seasonal_max_level(self) -> int:
        """Return the configured max ventilation level for the current season."""
        options = self._entry.options
        if self._season == SEASON_WINTER:
            return int(options.get(CONF_EXTRA_VENT_WINTER_LEVEL, DEFAULT_EXTRA_VENT_WINTER_LEVEL))
        return int(options.get(CONF_EXTRA_VENT_SUMMER_LEVEL, DEFAULT_EXTRA_VENT_SUMMER_LEVEL))

    # ------------------------------------------------------------------
    # Parameter lookup helpers
    # ------------------------------------------------------------------

    def _find_param_value_id(self, param_id: int) -> int | None:
        """Find the value_id for a parameter across all systems and components."""
        data = self._coordinator.data
        if not data:
            return None

        for device in data.values():
            for component in device.get("components", []):
                param = component.get("parameters", {}).get(param_id)
                if param is not None:
                    value_id = param.get("value_id")
                    if value_id is not None:
                        return int(value_id)
        return None

    def _build_mode_and_level_params(
        self,
        mode_value: str,
        level_value: str,
    ) -> list[tuple[int, str]]:
        """Build a param list for writing operating mode and ventilation level.

        Returns an empty list if the required value_ids cannot be found.
        """
        mode_vid = self._find_param_value_id(PARAM_OPERATING_MODE)
        level_vid = self._find_param_value_id(PARAM_VENTILATION_LEVEL)

        if mode_vid is None or level_vid is None:
            _LOGGER.warning(
                "Cannot build write params: mode_vid=%s, level_vid=%s",
                mode_vid,
                level_vid,
            )
            return []

        return [(mode_vid, mode_value), (level_vid, level_value)]

    def _get_system_and_gateway_ids(self) -> tuple[int | None, int | None]:
        """Return the (system_id, gateway_id) from the first system in coordinator data."""
        data = self._coordinator.data
        if not data:
            return None, None

        for system_id, device in data.items():
            gateway_id = device.get("gateway_id")
            if gateway_id is not None:
                return system_id, gateway_id

        return None, None

    # ------------------------------------------------------------------
    # Timer cancellation helpers
    # ------------------------------------------------------------------

    def _cancel_boost_timer(self) -> None:
        """Cancel the boost timer if active."""
        if self._boost_timer_unsub is not None:
            self._boost_timer_unsub()
            self._boost_timer_unsub = None
