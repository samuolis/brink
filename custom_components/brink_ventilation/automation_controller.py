"""Automation controller for Brink Home ventilation.

Implements a 3-state state machine (IDLE / BASE / BOOSTED) that manages
seasonal ventilation levels, humidity-spike detection, and a resilient
write queue that retries failed API writes on the next coordinator refresh.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .core.brink_home_cloud import BrinkAuthError
from .const import (
    BOOST_TRIGGER_HUMIDITY,
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
    DOMAIN,
    EVENT_BOOST_ACTIVATED,
    EVENT_BOOST_DEACTIVATED,
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
        IDLE  --(adaptive selected)-->  BASE
        BASE  --(humidity spike / button)-->  BOOSTED
        BOOSTED  --(timer expires)-->  BASE
        BASE / BOOSTED  --(adaptive deselected)-->  IDLE
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

        # Two-point humidity tracking: entity_id -> (monotonic_timestamp, value)
        self._humidity_previous: dict[str, tuple[float, float]] = {}
        # Last computed rate per sensor: entity_id -> rate (%/min)
        self._humidity_rates: dict[str, float] = {}

        # Resilient write queue -- stores the most recent desired params on failure
        self._pending_writes: list[tuple[int, str]] | None = None

        # Track whether automation was in BASE before boost (for correct return state)
        self._was_in_base_before_boost: bool = False

        self._boost_end_monotonic: float = 0.0

        self._boost_pending: bool = False
        self._pending_task: asyncio.Task[None] | None = None

        # Boost trigger info (None = manual, set only for automation triggers)
        self._boost_trigger: str | None = None
        self._boost_trigger_entity: str | None = None
        self._boost_trigger_rate: float | None = None

        # Unsub handles
        self._boost_timer_unsub: CALLBACK_TYPE | None = None
        self._countdown_timer_unsub: CALLBACK_TYPE | None = None
        self._humidity_timer_unsub: CALLBACK_TYPE | None = None

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
        remaining = self._boost_end_monotonic - time.monotonic()
        return max(0, math.ceil(remaining / 60))

    @property
    def has_pending_writes(self) -> bool:
        """Return True if there are pending writes awaiting retry."""
        return self._pending_writes is not None

    @property
    def boost_trigger(self) -> str | None:
        """Return the trigger type for the current boost, or None for manual."""
        if self._state != AutomationState.BOOSTED:
            return None
        return self._boost_trigger

    @property
    def boost_trigger_entity(self) -> str | None:
        """Return the entity_id that triggered the boost (humidity spike only)."""
        if self._state != AutomationState.BOOSTED:
            return None
        return self._boost_trigger_entity

    @property
    def boost_trigger_rate(self) -> float | None:
        """Return the humidity rate that triggered the boost (%/min)."""
        if self._state != AutomationState.BOOSTED:
            return None
        return self._boost_trigger_rate

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

    @property
    def humidity_deltas(self) -> dict[str, float]:
        """Return current humidity rate of change (%/min) for each monitored sensor.

        Returns a dict of entity_id -> rate value. Rate is 0.0 when the
        sensor value has not changed since the last timer tick.
        """
        return dict(self._humidity_rates)

    @property
    def max_humidity_delta(self) -> float:
        """Return the maximum humidity rate of change (%/min) across all sensors.

        This is the most useful single number for the user — shows the highest
        spike rate happening right now across all sensors.
        """
        deltas = self.humidity_deltas
        if not deltas:
            return 0.0
        return max(deltas.values())

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def async_start_humidity_monitoring(self) -> None:
        """Start humidity timer for delta tracking, independent of automation state.

        Called during setup so the humidity delta sensors always have data,
        even when Adaptive (HA) mode is not active.
        """
        self._start_humidity_timer()

    async def async_activate(self) -> None:
        """Transition IDLE -> BASE: start seasonal ventilation and humidity monitoring."""
        if self._state != AutomationState.IDLE:
            _LOGGER.debug(
                "async_activate called in state %s, expected IDLE", self._state
            )
            return

        self._state = AutomationState.BASE

        # Ensure humidity timer is running (may already be from monitoring)
        self._start_humidity_timer()

        # Persist adaptive mode active flag for startup recovery
        self._hass.config_entries.async_update_entry(
            self._entry,
            options={**self._entry.options, "adaptive_active": True},
        )

        base_level = await self._async_apply_seasonal_level(boosted=False)

        _LOGGER.info(
            "Automation activated: season=%s, base_level=%s",
            self._season,
            base_level,
        )

    async def async_deactivate(self) -> None:
        """Transition any state -> IDLE: cancel timers but keep humidity monitoring.

        Humidity timer remains active so the delta sensors continue to
        show data even when Adaptive (HA) mode is not active.
        """
        _LOGGER.info("Automation deactivating from state %s", self._state)

        self._cancel_pending_task()
        self._boost_pending = False
        self._cancel_boost_timer()
        self._cancel_countdown_timer()
        self._pending_writes = None
        self._was_in_base_before_boost = False
        self._boost_end_monotonic = 0.0
        self._clear_boost_trigger()
        self._state = AutomationState.IDLE

        # Clear adaptive mode active flag
        new_opts = {**self._entry.options, "adaptive_active": False}
        new_opts.pop("ha_automated_active", None)  # migrate old key
        if self._entry.options.get("adaptive_active", False) or self._entry.options.get("ha_automated_active", False):
            self._hass.config_entries.async_update_entry(
                self._entry,
                options=new_opts,
            )

    async def async_activate_extra_ventilation(
        self,
        trigger: str | None = None,
        trigger_entity: str | None = None,
        trigger_rate: float | None = None,
    ) -> None:
        """Activate extra ventilation boost (shared by button and humidity trigger).

        Sets the device to the seasonal max level in manual mode and starts
        the boost timer.

        Args:
            trigger: Trigger type (e.g. BOOST_TRIGGER_HUMIDITY) or None for manual.
            trigger_entity: Entity ID that caused the trigger (humidity sensor).
            trigger_rate: Humidity rate of change that triggered the boost (%/min).
        """
        self._boost_pending = False
        self._was_in_base_before_boost = self._state == AutomationState.BASE

        # Store trigger info (None = manual)
        self._boost_trigger = trigger
        self._boost_trigger_entity = trigger_entity
        self._boost_trigger_rate = trigger_rate

        duration_minutes: int = int(
            self._entry.options.get(CONF_EXTRA_VENT_DURATION, DEFAULT_EXTRA_VENT_DURATION)
        )

        max_level = await self._async_apply_seasonal_level(boosted=True)

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

        # Fire logbook event
        self._fire_boost_activated_event(max_level, duration_minutes)

        # Trigger immediate entity update so switch/sensor reflect new state
        self._coordinator.async_set_updated_data(self._coordinator.data)

        _LOGGER.info(
            "Extra ventilation activated: season=%s, max_level=%s, duration=%d min, trigger=%s",
            self._season,
            max_level,
            duration_minutes,
            trigger or "manual",
        )

    async def async_cancel_extra_ventilation(self) -> None:
        """Cancel an active extra ventilation boost.

        Returns to BASE if adaptive mode was active before the boost,
        otherwise returns to IDLE.
        """
        if self._state != AutomationState.BOOSTED:
            return

        self._cancel_boost_timer()
        self._cancel_countdown_timer()

        # Fire deactivated event before clearing state
        self._fire_boost_deactivated_event("cancelled")

        self._clear_boost_trigger()

        if self._was_in_base_before_boost:
            _LOGGER.info("Extra ventilation cancelled, returning to BASE")
            self._state = AutomationState.BASE
            await self._async_apply_seasonal_level(boosted=False)
        else:
            _LOGGER.info("Extra ventilation cancelled, returning to IDLE")
            self._state = AutomationState.IDLE

        # Trigger immediate entity update so switch/sensor reflect new state
        self._coordinator.async_set_updated_data(self._coordinator.data)

    async def async_on_coordinator_update(self) -> None:
        """Handle coordinator data refresh: re-evaluate season and retry writes.

        Season is always evaluated (so the season sensor works regardless of
        automation state), but ventilation level changes only happen when
        Adaptive (HA) mode is active (BASE or BOOSTED).
        """
        old_season = self._season
        self._season = self._evaluate_season()

        if self._state == AutomationState.IDLE:
            return

        if old_season != self._season and self._season is not None:
            _LOGGER.info("Season changed: %s -> %s", old_season, self._season)
            await self._async_apply_seasonal_level(
                boosted=(self._state == AutomationState.BOOSTED)
            )

        await self._async_retry_pending_writes()

    async def async_restore_state(self) -> None:
        """Restore automation state after HA restart.

        Checks entry.options for the adaptive_active flag. Also migrates the
        old ha_automated_active key for backward compatibility.
        """
        active = self._entry.options.get(
            "adaptive_active",
            self._entry.options.get("ha_automated_active", False),
        )
        if active:
            _LOGGER.info("Restoring adaptive mode state after restart")
            # Migrate old key if present
            if "ha_automated_active" in self._entry.options:
                new_opts = {**self._entry.options, "adaptive_active": True}
                new_opts.pop("ha_automated_active", None)
                self._hass.config_entries.async_update_entry(
                    self._entry, options=new_opts
                )
            # Reset state to IDLE so async_activate can transition properly
            self._state = AutomationState.IDLE
            await self.async_activate()

    async def async_options_updated(self) -> None:
        """Handle options flow update: restart humidity timer and re-evaluate season."""
        # Always restart humidity timer (sensors may have changed)
        # This ensures delta sensors work even when not in Adaptive (HA) mode
        self._cancel_humidity_timer()
        self._humidity_previous.clear()
        self._humidity_rates.clear()
        self._start_humidity_timer()

        if self._state == AutomationState.IDLE:
            return

        # Re-evaluate season with potentially new threshold
        old_season = self._season
        self._season = self._evaluate_season()

        if old_season != self._season and self._season is not None:
            _LOGGER.info(
                "Season changed after options update: %s -> %s",
                old_season,
                self._season,
            )
            await self._async_apply_seasonal_level(
                boosted=(self._state == AutomationState.BOOSTED)
            )

    async def async_cleanup(self) -> None:
        """Cancel all timers, clear state."""
        self._cancel_pending_task()
        self._boost_pending = False
        self._cancel_boost_timer()
        self._cancel_countdown_timer()
        self._cancel_humidity_timer()
        self._humidity_previous.clear()
        self._humidity_rates.clear()
        self._pending_writes = None
        self._boost_end_monotonic = 0.0
        self._clear_boost_trigger()
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
        except BrinkAuthError:
            _LOGGER.error(
                "Write failed due to authentication error, not retrying: %s",
                params,
            )
            self._pending_writes = None
            return
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
            # Fire deactivated event before clearing state
            self._fire_boost_deactivated_event("timer_expired")
            self._clear_boost_trigger()

            if self._was_in_base_before_boost:
                _LOGGER.info("Boost timer expired, transitioning to BASE")
                self._state = AutomationState.BASE

                self._cancel_pending_task()
                self._pending_task = self._hass.async_create_task(
                    self._safe_apply_seasonal_level(boosted=False),
                    "brink_ventilation_boost_return_to_base",
                )

                # Humidity monitoring resumes automatically since the timer
                # checks for BASE state — no need to restart it
            else:
                _LOGGER.info(
                    "Boost timer expired, transitioning to IDLE "
                    "(boost was triggered outside adaptive mode)"
                )
                self._state = AutomationState.IDLE

            # Trigger immediate entity update so switch/sensor reflect new state
            self._coordinator.async_set_updated_data(self._coordinator.data)
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
    # Humidity monitoring (timer-based two-point comparison)
    # ------------------------------------------------------------------

    _HUMIDITY_CHECK_INTERVAL = 60  # seconds between humidity checks

    def _start_humidity_timer(self) -> None:
        """Start a periodic 60-second timer to check humidity sensors."""
        self._cancel_humidity_timer()
        sensors = self.configured_humidity_sensors
        if not sensors:
            _LOGGER.debug("No humidity sensors configured, skipping timer")
            return

        @callback
        def _humidity_tick(_now: Any) -> None:
            """Read each humidity sensor, compute rate, check for spikes."""
            now = time.monotonic()
            spike_entity: str | None = None
            spike_rate: float = 0.0

            for entity_id in self.configured_humidity_sensors:
                state = self._hass.states.get(entity_id)
                if state is None or state.state in (None, "", "unavailable", "unknown"):
                    continue

                try:
                    value = float(state.state)
                except (ValueError, TypeError):
                    continue

                if math.isnan(value) or math.isinf(value):
                    continue
                if value < 0.0 or value > 100.0:
                    continue

                if entity_id not in self._humidity_previous:
                    # First reading — store and move on
                    self._humidity_previous[entity_id] = (now, value)
                    self._humidity_rates[entity_id] = 0.0
                    continue

                old_time, old_value = self._humidity_previous[entity_id]
                elapsed_minutes = (now - old_time) / 60.0

                if elapsed_minutes > 0.0 and abs(value - old_value) > 0.009:
                    rate = round((value - old_value) / elapsed_minutes, 1)
                    rate = max(-50.0, min(50.0, rate))
                    self._humidity_rates[entity_id] = rate

                    # Track highest spike for boost trigger
                    if rate > spike_rate:
                        spike_rate = rate
                        spike_entity = entity_id
                else:
                    self._humidity_rates[entity_id] = 0.0

                # Always replace previous (keeps elapsed ~1 min for sensitivity)
                self._humidity_previous[entity_id] = (now, value)

            # Spike detection — only trigger boost when in BASE state
            if (
                spike_entity is not None
                and self._state == AutomationState.BASE
                and not self._boost_pending
            ):
                threshold: float = float(
                    self._entry.options.get(
                        CONF_HUMIDITY_SPIKE_THRESHOLD,
                        DEFAULT_HUMIDITY_SPIKE_THRESHOLD,
                    )
                )
                if spike_rate >= threshold:
                    _LOGGER.info(
                        "Humidity spike detected on %s: %.1f %%/min "
                        "(threshold %.1f %%/min)",
                        spike_entity,
                        spike_rate,
                        threshold,
                    )
                    self._boost_pending = True
                    try:
                        self._cancel_pending_task()
                        self._pending_task = self._hass.async_create_task(
                            self._safe_activate_extra_ventilation(
                                trigger_entity=spike_entity,
                                trigger_rate=spike_rate,
                            ),
                            "brink_ventilation_humidity_boost",
                        )
                    except Exception:
                        self._boost_pending = False
                        _LOGGER.exception("Failed to create humidity boost task")

            # Trigger entity state update so delta sensors reflect new rates
            self._coordinator.async_set_updated_data(self._coordinator.data)

            # Reschedule
            self._humidity_timer_unsub = async_call_later(
                self._hass, self._HUMIDITY_CHECK_INTERVAL, _humidity_tick
            )

        self._humidity_timer_unsub = async_call_later(
            self._hass, self._HUMIDITY_CHECK_INTERVAL, _humidity_tick
        )
        _LOGGER.debug("Started humidity timer for: %s", sensors)

    def _cancel_humidity_timer(self) -> None:
        """Cancel the humidity check timer if active."""
        if self._humidity_timer_unsub is not None:
            self._humidity_timer_unsub()
            self._humidity_timer_unsub = None

    # ------------------------------------------------------------------
    # Safe wrappers for fire-and-forget tasks
    # ------------------------------------------------------------------

    async def _safe_activate_extra_ventilation(
        self,
        trigger_entity: str | None = None,
        trigger_rate: float | None = None,
    ) -> None:
        """Activate extra ventilation with error logging for fire-and-forget tasks."""
        try:
            await self.async_activate_extra_ventilation(
                trigger=BOOST_TRIGGER_HUMIDITY if trigger_entity else None,
                trigger_entity=trigger_entity,
                trigger_rate=trigger_rate,
            )
        except Exception:
            _LOGGER.exception("Error activating extra ventilation from humidity spike")

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

    async def _async_apply_seasonal_level(self, boosted: bool = False) -> int:
        """Evaluate season and write the appropriate ventilation level. Returns the level used."""
        self._season = self._evaluate_season()
        level = self._get_seasonal_max_level() if boosted else self._get_seasonal_base_level()
        params = self._build_mode_and_level_params(mode_value="1", level_value=str(level))
        if params:
            await self.async_write_params(params)
        return level

    async def _safe_apply_seasonal_level(self, boosted: bool = False) -> None:
        """Apply seasonal level with error logging for fire-and-forget tasks."""
        try:
            await self._async_apply_seasonal_level(boosted=boosted)
        except Exception:
            _LOGGER.exception("Error applying seasonal level from timer callback")

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
    # Boost trigger helpers
    # ------------------------------------------------------------------

    def _clear_boost_trigger(self) -> None:
        """Clear boost trigger info."""
        self._boost_trigger = None
        self._boost_trigger_entity = None
        self._boost_trigger_rate = None

    def _fire_boost_activated_event(
        self, level: int, duration_minutes: int
    ) -> None:
        """Fire a logbook event when extra ventilation boost starts."""
        event_data: dict[str, Any] = {
            "entity_id": self._get_switch_entity_id(),
            "duration": duration_minutes,
            "level": level,
            "season": self._season,
        }
        if self._boost_trigger == BOOST_TRIGGER_HUMIDITY:
            event_data["trigger"] = BOOST_TRIGGER_HUMIDITY
            if self._boost_trigger_entity:
                event_data["sensor"] = self._boost_trigger_entity
            if self._boost_trigger_rate is not None:
                event_data["rate"] = self._boost_trigger_rate
        self._hass.bus.async_fire(EVENT_BOOST_ACTIVATED, event_data)

    def _fire_boost_deactivated_event(self, reason: str) -> None:
        """Fire a logbook event when extra ventilation boost ends."""
        event_data: dict[str, Any] = {
            "entity_id": self._get_switch_entity_id(),
            "reason": reason,
        }
        if self._boost_trigger == BOOST_TRIGGER_HUMIDITY:
            event_data["trigger"] = BOOST_TRIGGER_HUMIDITY
        self._hass.bus.async_fire(EVENT_BOOST_DEACTIVATED, event_data)

    def _get_switch_entity_id(self) -> str:
        """Return the entity_id for the extra ventilation switch."""
        data = self._coordinator.data
        if data:
            for system_id in data:
                return f"switch.brink_{system_id}_extra_ventilation"
        return f"switch.{DOMAIN}_extra_ventilation"

    # ------------------------------------------------------------------
    # Timer and task cancellation helpers
    # ------------------------------------------------------------------

    def _cancel_pending_task(self) -> None:
        """Cancel the pending async task if running."""
        if self._pending_task and not self._pending_task.done():
            self._pending_task.cancel()
        self._pending_task = None

    def _cancel_boost_timer(self) -> None:
        """Cancel the boost timer if active."""
        if self._boost_timer_unsub is not None:
            self._boost_timer_unsub()
            self._boost_timer_unsub = None
