"""Coordinator for the Brink Home integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from aiohttp import (
    ClientError,
    ClientResponseError,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import async_get_devices
from .core.brink_home_cloud import (
    BrinkApiError,
    BrinkAuthError,
    BrinkHomeCloud,
)
from .models import BrinkAlert, BrinkDeviceData

_LOGGER = logging.getLogger(__name__)


class BrinkCoordinator(
    DataUpdateCoordinator[dict[int, BrinkDeviceData]]
):
    """Coordinate Brink Home API updates."""

    api_is_online: bool = False
    api_error: str | None = None
    api_error_code: int | None = None
    api_error_type: str | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        brink_client: BrinkHomeCloud,
        scan_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        self.config_entry = config_entry
        self._client = brink_client
        update_interval = timedelta(seconds=scan_interval)

        super().__init__(
            hass,
            logger=_LOGGER,
            name="Brink Home",
            config_entry=config_entry,
            update_interval=update_interval,
        )

    @property
    def has_blocking_error(self) -> bool:
        """Return whether any device has an active blocking error."""
        if self.data is None:
            return False
        return any(device.has_blocking_error for device in self.data.values())

    @property
    def active_alerts(self) -> list[BrinkAlert]:
        """Return all active alerts."""
        if self.data is None:
            return []

        return [
            alert
            for device in self.data.values()
            for alert in device.alerts
        ]

    async def _async_update_data(
        self,
    ) -> dict[int, BrinkDeviceData]:
        """Fetch the latest data from Brink."""
        _LOGGER.debug("Fetching device data from Brink")

        try:
            data = await async_get_devices(self._client)

        except BrinkAuthError as err:
            self._set_api_error(
                error=str(err),
                error_code=401,
                error_type="authentication",
            )
            _LOGGER.exception("Brink authentication error")
            raise ConfigEntryAuthFailed from err

        except ClientResponseError as err:
            self._set_api_error(
                error=(
                    f"HTTP {err.status}: "
                    f"{err.message or 'HTTP request failed'}"
                ),
                error_code=err.status,
                error_type="http",
            )
            _LOGGER.exception(
                "Brink HTTP error: status=%s",
                err.status,
            )

            if err.status == 401:
                raise ConfigEntryAuthFailed from err

            raise UpdateFailed(err) from err

        except (ClientError, TimeoutError) as err:
            self._set_api_error(
                error=str(err),
                error_code=None,
                error_type="connection",
            )
            _LOGGER.exception("Brink connection error")
            raise UpdateFailed(err) from err

        except BrinkApiError as err:
            self._set_api_error(
                error=str(err),
                error_code=err.error_code,
                error_type=err.error_type,
            )
            _LOGGER.exception("Brink API error")
            raise UpdateFailed(err) from err

        self._set_api_online()

        return data

    def _set_api_online(self) -> None:
        """Set the API status to online."""
        self.api_is_online = True
        self.api_error = None
        self.api_error_code = None
        self.api_error_type = None

    def _set_api_error(
        self,
        *,
        error: str,
        error_code: int | None,
        error_type: str,
    ) -> None:
        """Set the API status to offline."""
        self.api_is_online = False
        self.api_error = error
        self.api_error_code = error_code
        self.api_error_type = error_type

    async def old_async_update_data(
        self,
    ) -> dict[int, BrinkDeviceData]:
        """Fetch the latest data from Brink."""
        _LOGGER.debug("Fetching device data from Brink")

        try:
            return await async_get_devices(self._client)
        except BrinkAuthError as err:
            _LOGGER.exception("Brink authentication error")
            raise ConfigEntryAuthFailed from err
        except ClientResponseError as err:
            _LOGGER.exception(
                "Brink HTTP error: status=%s",
                err.status,
            )
            if err.status == 401:
                raise ConfigEntryAuthFailed from err
            raise UpdateFailed(err) from err
        except (ClientError, TimeoutError) as err:
            _LOGGER.exception("Brink connection error")
            raise UpdateFailed(err) from err
        except BrinkApiError as err:
            _LOGGER.exception("Brink API error")
            raise UpdateFailed(err) from err
