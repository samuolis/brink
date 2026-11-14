"""Regression tests preventing private Brink API data from entering logs."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientConnectorError, ClientResponseError, ServerDisconnectedError
from homeassistant.core import HomeAssistant

from custom_components.brink_ventilation.const import DOMAIN
from custom_components.brink_ventilation.coordinator import BrinkCoordinator
from custom_components.brink_ventilation.core.brink_home_cloud import BrinkHomeCloud
from tests.ha_test_support import MockConfigEntry


@pytest.mark.asyncio
async def test_oidc_token_response_is_not_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Keep access and refresh tokens out of DEBUG logs on token exchange."""
    response = MagicMock(status=200)
    response.json = AsyncMock(
        return_value={
            "access_token": "secret-access-token-for-test",
            "refresh_token": "secret-refresh-token-for-test",
            "expires_in": 3600,
        }
    )
    response.release = AsyncMock()
    session = MagicMock()
    session.post = AsyncMock(return_value=response)
    client = BrinkHomeCloud(session, "synthetic-user", "synthetic-password")

    with caplog.at_level(logging.DEBUG):
        await client._exchange_code_for_tokens("synthetic-code", "synthetic-verifier")

    assert client._access_token == "secret-access-token-for-test"
    assert client._refresh_token == "secret-refresh-token-for-test"
    assert "secret-access-token-for-test" not in caplog.text
    assert "secret-refresh-token-for-test" not in caplog.text


@pytest.mark.asyncio
async def test_system_account_data_is_not_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Keep system names, serials and ownership information out of logs."""
    response = MagicMock()
    response.json = AsyncMock(
        return_value={
            "items": [
                {
                    "systemShareId": 101,
                    "systemName": "private-device-for-test",
                    "serialNumber": "private-serial-for-test",
                    "ownerGroupName": "private-owner-for-test",
                    "accessLevel": "owner",
                    "isSystemOwner": True,
                }
            ]
        }
    )
    response.release = AsyncMock()
    client = BrinkHomeCloud(MagicMock(), "synthetic-user", "synthetic-password")
    client._api_request = AsyncMock(return_value=response)

    with caplog.at_level(logging.DEBUG):
        systems = await client.get_systems()

    assert len(systems) == 1
    assert systems[0]["system_id"] == 101
    for private_value in (
        "private-device-for-test",
        "private-serial-for-test",
        "private-owner-for-test",
    ):
        assert private_value not in caplog.text


@pytest.mark.usefixtures("enable_custom_integrations")
@pytest.mark.parametrize("failure", ["http", "connector", "retry"])
async def test_coordinator_logs_sanitized_request_errors(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, failure: str
) -> None:
    """Render actual coordinator tracebacks without private upstream causes."""
    private_text = "synthetic-private-request-detail"
    private_url = "https://example.invalid/?token=synthetic-private-token"
    session = MagicMock()
    client = BrinkHomeCloud(session, "synthetic-user", "synthetic-password")
    client._ensure_token = AsyncMock()
    if failure == "http":
        request_info = MagicMock(real_url=private_url)
        error = ClientResponseError(request_info, (), status=503, message=private_text)
        response = MagicMock(status=503)
        response.raise_for_status.side_effect = error
        response.release = AsyncMock()
        session.request = AsyncMock(return_value=response)
    elif failure == "connector":
        key = MagicMock(host=private_url, port=443, ssl=True)
        error = ClientConnectorError(key, OSError(private_text))
        session.request = AsyncMock(side_effect=error)
    else:
        session.request = AsyncMock(side_effect=ServerDisconnectedError(private_text))

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    coordinator = BrinkCoordinator(hass, entry, client, scan_interval=60)

    async def fetch_devices(_: BrinkHomeCloud) -> None:
        """Exercise the real request path through the coordinator boundary."""
        await client.get_systems()

    with (
        patch(
            "custom_components.brink_ventilation.coordinator.async_get_devices",
            side_effect=fetch_devices,
        ),
        patch(
            "custom_components.brink_ventilation.core.brink_home_cloud.asyncio.sleep",
            new_callable=AsyncMock,
        ),
        caplog.at_level(logging.ERROR),
    ):
        await coordinator.async_refresh()

    assert not coordinator.last_update_success
    assert "Brink API error" in caplog.text
    assert private_text not in caplog.text
    assert private_url not in caplog.text
    assert "synthetic-private-token" not in caplog.text
    if failure == "http":
        assert "HTTP 503" in caplog.text
        assert coordinator.api_error_code == 503
