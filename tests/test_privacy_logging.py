"""Regression tests preventing private Brink API data from entering logs."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.brink_ventilation.core.brink_home_cloud import BrinkHomeCloud


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
