"""Local API client for Brink Home devices."""

from __future__ import annotations

import logging

from aiohttp import ClientError, ClientSession

_LOGGER = logging.getLogger(__name__)

HOST = "brink.local"


class BrinkHomeLocalError(Exception):
    """Raised when communication with the local Brink device fails."""


class BrinkHomeLocalClient:
    """Client for the local Brink Home web interface."""

    def __init__(
        self,
        session: ClientSession,
        host: str = "brink.local",
        *,
        port: int = 80,
    ) -> None:
        """Initialize the local Brink client."""
        self._session = session
        self._base_url = f"http://{host}:{port}"

    async def async_get_uid_values(self) -> dict[str, str]:
        """Return the raw UID values from the local web interface."""
        return await self._async_get_json("actuals.json")

    async def async_get_commands(self) -> dict[str, object]:
        """Return the supported commands."""
        return await self._async_get_json("commands.json")

    async def async_get_configuration(self) -> dict[str, object]:
        """Return the configuration."""
        return await self._async_get_json("configuration.json")

    async def _async_get_json(
        self,
        endpoint: str,
    ) -> dict[str, object]:
        """Fetch a JSON endpoint."""
        url = f"{self._base_url}/{endpoint}"

        _LOGGER.debug("Fetching Brink local endpoint %s", url)

        try:
            async with self._session.get(url) as response:
                response.raise_for_status()

                payload = await response.json(content_type=None)

        except ClientError as err:
            raise BrinkHomeLocalError(
                f"Failed to fetch '{endpoint}' from {self._base_url}"
            ) from err

        _LOGGER.debug(
            "Received %d keys from %s",
            len(payload),
            endpoint,
        )

        return payload
