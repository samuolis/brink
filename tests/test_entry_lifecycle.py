"""Exercise Brink config-entry resource ownership with synthetic transports."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientConnectionError, ClientResponseError
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.brink_ventilation import async_setup_entry, async_unload_entry
from custom_components.brink_ventilation.const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
)
from custom_components.brink_ventilation.core.brink_home_cloud import BrinkAuthError
from tests.ha_test_support import MockConfigEntry


def _mock_hass() -> MagicMock:
    """Provide only the HA entry storage and awaited platform methods needed."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    return hass


def _mock_client() -> MagicMock:
    """Create a cloud client that cannot contact a real Brink account."""
    client = MagicMock()
    client.login = AsyncMock()
    client.close = AsyncMock()
    return client


def _mock_config_entry() -> MockConfigEntry:
    """Keep all account identifiers and credentials synthetic."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "synthetic-account", CONF_PASSWORD: "synthetic-secret"},
    )


def _http_error(status: int) -> ClientResponseError:
    """Build an aiohttp error without making an HTTP request."""
    return ClientResponseError(
        MagicMock(real_url="https://example.invalid/"),
        (),
        status=status,
        message="synthetic upstream failure",
    )


@pytest.mark.parametrize(
    ("failure", "expected_exception"),
    [
        pytest.param(
            BrinkAuthError("synthetic invalid login", is_credentials_error=True),
            ConfigEntryAuthFailed,
            id="invalid-login",
        ),
        pytest.param(_http_error(401), ConfigEntryAuthFailed, id="http-401"),
        pytest.param(_http_error(503), ConfigEntryNotReady, id="http-503"),
        pytest.param(
            ClientConnectionError("synthetic network failure"),
            ConfigEntryNotReady,
            id="network-failure",
        ),
        pytest.param(
            TimeoutError("synthetic timeout"), ConfigEntryNotReady, id="timeout"
        ),
    ],
)
async def test_failed_login_closes_client_without_forwarding_platforms(
    failure: Exception,
    expected_exception: type[Exception],
) -> None:
    """Reject permanent or transient login failures before exposing entities."""
    hass = _mock_hass()
    entry = _mock_config_entry()
    client = _mock_client()
    client.login.side_effect = failure
    with (
        patch(
            "custom_components.brink_ventilation.BrinkHomeCloud", return_value=client
        ),
        patch("custom_components.brink_ventilation.async_get_clientsession"),
        pytest.raises(expected_exception) as captured_error,
    ):
        await async_setup_entry(hass, entry)

    assert captured_error.value.__cause__ is failure
    client.close.assert_awaited_once()
    hass.config_entries.async_forward_entry_setups.assert_not_awaited()
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_successful_setup_registers_runtime_and_unloads_safely() -> None:
    """Expose runtime only after login and refresh, and close on successful unload."""
    hass = _mock_hass()
    entry = _mock_config_entry()
    client = _mock_client()
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    with (
        patch(
            "custom_components.brink_ventilation.BrinkHomeCloud", return_value=client
        ),
        patch(
            "custom_components.brink_ventilation.BrinkCoordinator",
            return_value=coordinator,
        ),
        patch("custom_components.brink_ventilation.async_get_clientsession"),
    ):
        assert await async_setup_entry(hass, entry) is True

    client.login.assert_awaited_once()
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    hass.config_entries.async_forward_entry_setups.assert_awaited_once()
    assert hass.data[DOMAIN][entry.entry_id] == {
        DATA_CLIENT: client,
        DATA_COORDINATOR: coordinator,
    }

    assert await async_unload_entry(hass, entry) is True
    assert entry.entry_id not in hass.data[DOMAIN]
    client.close.assert_awaited_once()


async def test_failed_platform_unload_retains_client_and_runtime() -> None:
    """Keep runtime alive when Home Assistant could not unload its platforms."""
    hass = _mock_hass()
    entry = _mock_config_entry()
    client = _mock_client()
    coordinator = MagicMock()
    hass.data[DOMAIN] = {
        entry.entry_id: {DATA_CLIENT: client, DATA_COORDINATOR: coordinator}
    }
    hass.config_entries.async_unload_platforms.return_value = False

    assert await async_unload_entry(hass, entry) is False
    assert hass.data[DOMAIN][entry.entry_id][DATA_CLIENT] is client
    client.close.assert_not_awaited()


async def test_initial_refresh_failure_closes_transport_without_forwarding() -> None:
    """Never expose platforms after an unsuccessful first coordinator refresh."""
    hass = _mock_hass()
    entry = _mock_config_entry()
    client = _mock_client()
    coordinator = MagicMock()
    refresh_error = UpdateFailed("synthetic refresh failure")
    coordinator.async_config_entry_first_refresh = AsyncMock(side_effect=refresh_error)

    with (
        patch(
            "custom_components.brink_ventilation.BrinkHomeCloud", return_value=client
        ),
        patch(
            "custom_components.brink_ventilation.BrinkCoordinator",
            return_value=coordinator,
        ),
        patch("custom_components.brink_ventilation.async_get_clientsession"),
        pytest.raises(UpdateFailed) as captured_error,
    ):
        await async_setup_entry(hass, entry)

    assert captured_error.value is refresh_error
    client.close.assert_awaited_once()
    assert entry.entry_id not in hass.data.get(DOMAIN, {})
    hass.config_entries.async_forward_entry_setups.assert_not_awaited()


async def test_first_refresh_cancellation_does_not_leave_runtime() -> None:
    """Propagate task cancellation while closing the owned cloud transport."""
    from asyncio import CancelledError

    hass = _mock_hass()
    entry = _mock_config_entry()
    client = _mock_client()
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock(
        side_effect=CancelledError()
    )
    with (
        patch(
            "custom_components.brink_ventilation.BrinkHomeCloud",
            return_value=client,
        ),
        patch(
            "custom_components.brink_ventilation.BrinkCoordinator",
            return_value=coordinator,
        ),
        patch("custom_components.brink_ventilation.async_get_clientsession"),
        pytest.raises(CancelledError),
    ):
        await async_setup_entry(hass, entry)

    client.close.assert_awaited_once()
    assert entry.entry_id not in hass.data.get(DOMAIN, {})
    hass.config_entries.async_forward_entry_setups.assert_not_awaited()


async def test_failed_platform_forwarding_cleans_up_owned_runtime() -> None:
    """Do not retain a closed client after Home Assistant fails to set up a platform."""
    hass = _mock_hass()
    entry = _mock_config_entry()
    client = _mock_client()
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    platform_error = RuntimeError("synthetic platform setup error")
    hass.config_entries.async_forward_entry_setups.side_effect = platform_error

    with (
        patch(
            "custom_components.brink_ventilation.BrinkHomeCloud",
            return_value=client,
        ),
        patch(
            "custom_components.brink_ventilation.BrinkCoordinator",
            return_value=coordinator,
        ),
        patch("custom_components.brink_ventilation.async_get_clientsession"),
        pytest.raises(RuntimeError) as caught,
    ):
        await async_setup_entry(hass, entry)

    assert caught.value is platform_error
    client.close.assert_awaited_once()
    assert entry.entry_id not in hass.data[DOMAIN]
