"""Verify coordinator status, authentication failures and recovery."""

from __future__ import annotations

from asyncio import CancelledError
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientConnectionError, ClientResponseError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.brink_ventilation.const import DOMAIN
from custom_components.brink_ventilation.coordinator import BrinkCoordinator
from custom_components.brink_ventilation.core.brink_home_cloud import (
    BrinkApiError,
    BrinkAuthError,
)
from tests.ha_test_support import MockConfigEntry


def _create_coordinator(hass: HomeAssistant) -> BrinkCoordinator:
    """Build a real coordinator with a synthetic config entry and no network."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    return BrinkCoordinator(hass, config_entry, MagicMock(), scan_interval=60)


def _http_error(status: int) -> ClientResponseError:
    """Produce a synthetic aiohttp response error without a real request."""
    request_info = MagicMock(real_url="https://example.invalid/api")
    return ClientResponseError(
        request_info,
        (),
        status=status,
        message="synthetic upstream failure",
    )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_successful_refresh_clears_previous_api_error(
    hass: HomeAssistant,
) -> None:
    """A recovered connection must clear every stale API diagnostic field."""
    coordinator = _create_coordinator(hass)
    coordinator._set_api_error(
        error="synthetic connection failure",
        error_code=503,
        error_type="http",
    )
    try:
        with patch(
            "custom_components.brink_ventilation.coordinator.async_get_devices",
            new_callable=AsyncMock,
            return_value={},
        ) as fetch_devices:
            assert await coordinator._async_update_data() == {}
        fetch_devices.assert_awaited_once()
        assert coordinator.api_is_online is True
        assert coordinator.api_error is None
        assert coordinator.api_error_code is None
        assert coordinator.api_error_type is None
    finally:
        await coordinator.async_shutdown()


@pytest.mark.usefixtures("enable_custom_integrations")
@pytest.mark.parametrize(
    ("api_error", "expected_exception", "expected_code", "expected_type"),
    [
        pytest.param(
            BrinkAuthError("synthetic credentials rejected", is_credentials_error=True),
            ConfigEntryAuthFailed,
            401,
            "authentication",
            id="login-rejected",
        ),
        pytest.param(
            _http_error(401), ConfigEntryAuthFailed, 401, "http", id="http-401"
        ),
        pytest.param(_http_error(503), UpdateFailed, 503, "http", id="http-503"),
        pytest.param(
            ClientConnectionError("synthetic connection interrupted"),
            UpdateFailed,
            None,
            "connection",
            id="connection-error",
        ),
        pytest.param(
            TimeoutError("synthetic timeout"),
            UpdateFailed,
            None,
            "connection",
            id="timeout",
        ),
        pytest.param(
            BrinkApiError(
                "synthetic API rejection", error_code=429, error_type="rate_limit"
            ),
            UpdateFailed,
            429,
            "rate_limit",
            id="vendor-api-error",
        ),
    ],
)
async def test_refresh_failure_classification(
    hass: HomeAssistant,
    api_error: Exception,
    expected_exception: type[Exception],
    expected_code: int | None,
    expected_type: str,
) -> None:
    """Classify failures without publishing a successful API status."""
    coordinator = _create_coordinator(hass)
    try:
        with (
            patch(
                "custom_components.brink_ventilation.coordinator.async_get_devices",
                new_callable=AsyncMock,
                side_effect=api_error,
            ),
            pytest.raises(expected_exception) as captured_error,
        ):
            await coordinator._async_update_data()
        assert captured_error.value.__cause__ is api_error
        assert coordinator.api_is_online is False
        assert coordinator.api_error_type == expected_type
        assert coordinator.api_error_code == expected_code
        assert coordinator.api_error is not None
    finally:
        await coordinator.async_shutdown()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_cancelled_refresh_propagates_without_false_health_status(
    hass: HomeAssistant,
) -> None:
    """Shutdown cancellation must not be relabeled as an API failure."""
    coordinator = _create_coordinator(hass)
    coordinator._set_api_online()
    try:
        with (
            patch(
                "custom_components.brink_ventilation.coordinator.async_get_devices",
                new_callable=AsyncMock,
                side_effect=CancelledError,
            ),
            pytest.raises(CancelledError),
        ):
            await coordinator._async_update_data()
        assert coordinator.api_is_online is True
        assert coordinator.api_error is None
    finally:
        await coordinator.async_shutdown()
