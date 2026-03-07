"""Brink Home Cloud API client using the v1.1 API with OIDC PKCE auth."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import secrets
import time
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlparse

import aiohttp
import async_timeout

from ..const import (
    API_V1_URL,
    OIDC_AUTH_URL,
    OIDC_CLIENT_ID,
    OIDC_REDIRECT_URI,
    OIDC_SCOPE,
    OIDC_TOKEN_URL,
    PARAM_NAME_MAP,
    WRITE_VALUE_STATE,
)
from ..translations import TRANSLATIONS

_LOGGER = logging.getLogger(__name__)
_TRUSTED_HOST = "www.brink-home.com"


class _InputFieldExtractor(HTMLParser):
    """Extract values from HTML input fields."""

    def __init__(self, target_names: set[str]) -> None:
        super().__init__()
        self._targets = {name.lower() for name in target_names}
        self.results: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "input":
            return
        attr_dict = {key.lower(): (value or "") for key, value in attrs}
        name = attr_dict.get("name", "").lower()
        if name in self._targets and "value" in attr_dict:
            self.results[name] = attr_dict["value"]


class BrinkAuthError(Exception):
    """Raised when Brink Home authentication fails."""

    def __init__(self, message: str, *, is_credentials_error: bool = False) -> None:
        super().__init__(message)
        self.is_credentials_error = is_credentials_error


class BrinkHomeCloud:
    """Interact with Brink Home through the v1.1 API."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str):
        self._session = session
        self._username = username
        self._password = password
        self._timeout = 20
        self._access_token: str | None = None
        self._token_expiry: float = 0.0
        self._refresh_token: str | None = None
        self._token_lock = asyncio.Lock()

    async def login(self) -> None:
        """Perform an OIDC login and cache the bearer token."""
        await self._oidc_login()

    async def close(self) -> None:
        """Clear sensitive state."""
        self._access_token = None
        self._token_expiry = 0.0
        self._refresh_token = None
        self._username = ""
        self._password = ""

    async def get_systems(self) -> list[dict[str, Any]]:
        """Return the systems visible to the current account."""
        response = await self._api_request("GET", f"{API_V1_URL}systems?pageSize=5")
        try:
            payload = await response.json()
        finally:
            await response.release()

        systems: list[dict[str, Any]] = []
        for item in payload.get("items", []):
            system_id = item.get("systemShareId")
            if system_id is None:
                continue
            systems.append(
                {
                    "system_id": system_id,
                    "name": item.get("systemName") or "Brink",
                    "serial_number": item.get("serialNumber"),
                    "gateway_state": item.get("gatewayState"),
                }
            )
        return systems

    async def get_device_data(self, system_id: int) -> dict[str, dict[str, Any]]:
        """Return a flattened parameter map for a system."""
        response = await self._api_request(
            "GET", f"{API_V1_URL}systems/{system_id}/uidescription"
        )
        try:
            payload = await response.json()
        finally:
            await response.release()

        parameters: dict[str, dict[str, Any]] = {}
        self._extract_parameters(
            (payload.get("root") or {}).get("navigationItems", []), parameters
        )
        return parameters

    async def write_parameters(
        self, system_id: int, params: list[tuple[int, str]]
    ) -> None:
        """Write parameter values to a system."""
        payload = {
            "writeValues": [
                {
                    "valueId": value_id,
                    "value": value,
                    "state": WRITE_VALUE_STATE,
                }
                for value_id, value in params
            ]
        }
        response = await self._api_request(
            "PUT",
            f"{API_V1_URL}systems/{system_id}/parameter-values",
            json_data=payload,
        )
        try:
            await response.read()
        finally:
            await response.release()

    async def _api_request(
        self,
        method: str,
        url: str,
        *,
        json_data: dict[str, Any] | None = None,
    ) -> aiohttp.ClientResponse:
        """Perform an authenticated v1.1 API request."""
        for attempt in range(2):
            await self._ensure_token()
            async with async_timeout.timeout(self._timeout):
                response = await self._session.request(
                    method,
                    url,
                    json=json_data,
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Accept": "application/json",
                    },
                )

            if response.status == 401 and attempt == 0:
                await response.release()
                async with self._token_lock:
                    self._token_expiry = 0.0
                    self._access_token = None
                continue

            if response.status == 401:
                await response.release()
                raise BrinkAuthError("Authentication failed after retry")

            response.raise_for_status()
            return response

        raise BrinkAuthError("Authentication failed before request")

    async def _ensure_token(self) -> None:
        """Ensure a usable bearer token is available."""
        if self._access_token and time.monotonic() < self._token_expiry:
            return

        async with self._token_lock:
            if self._access_token and time.monotonic() < self._token_expiry:
                return
            if self._refresh_token:
                try:
                    await self._refresh_access_token()
                    return
                except BrinkAuthError:
                    _LOGGER.info(
                        "Refresh token unavailable or invalid, falling back to full login"
                    )
            await self._oidc_login()

    async def _oidc_login(self) -> None:
        """Execute the OIDC Authorization Code + PKCE flow."""
        code_verifier = self._generate_code_verifier()
        code_challenge = self._generate_code_challenge(code_verifier)
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)

        jar = aiohttp.CookieJar(unsafe=False)
        async with aiohttp.ClientSession(cookie_jar=jar) as oidc_session:
            login_url, csrf_token, return_url = await self._fetch_login_page(
                oidc_session, code_challenge, state, nonce
            )
            authorization_code = await self._submit_login_credentials(
                oidc_session, login_url, csrf_token, return_url, state
            )

        await self._exchange_code_for_tokens(authorization_code, code_verifier)

    async def _fetch_login_page(
        self,
        session: aiohttp.ClientSession,
        code_challenge: str,
        state: str,
        nonce: str,
    ) -> tuple[str, str, str | None]:
        auth_params = {
            "client_id": OIDC_CLIENT_ID,
            "redirect_uri": OIDC_REDIRECT_URI,
            "response_type": "code",
            "scope": OIDC_SCOPE,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        async with async_timeout.timeout(30):
            response = await session.get(
                OIDC_AUTH_URL,
                params=auth_params,
                allow_redirects=True,
            )
            if response.status != 200:
                raise BrinkAuthError(
                    f"OIDC authorize failed with status {response.status}"
                )
            html = await response.text()
            login_url = str(response.url)
            await response.release()

        if not self._is_trusted_url(login_url):
            raise BrinkAuthError("OIDC login page redirected to an untrusted host")

        form_fields = self._extract_form_fields(html)
        csrf_token = form_fields.get("__requestverificationtoken")
        if not csrf_token:
            raise BrinkAuthError("Could not find CSRF token in OIDC login page")

        return login_url, csrf_token, form_fields.get("returnurl")

    async def _submit_login_credentials(
        self,
        session: aiohttp.ClientSession,
        login_url: str,
        csrf_token: str,
        return_url: str | None,
        expected_state: str,
    ) -> str:
        form_data = {
            "Username": self._username,
            "Password": self._password,
            "__RequestVerificationToken": csrf_token,
        }
        if return_url:
            if return_url.startswith("/") and not return_url.startswith("//"):
                form_data["ReturnUrl"] = return_url
            elif self._is_trusted_url(return_url):
                form_data["ReturnUrl"] = return_url

        async with async_timeout.timeout(30):
            response = await session.post(
                login_url,
                data=form_data,
                allow_redirects=False,
            )
            status = response.status
            location = response.headers.get("Location", "")
            body = await response.text()
            await response.release()

        if status in (301, 302, 303, 307):
            code = self._extract_code_from_redirect(location, expected_state)
            if code:
                return code
            code = await self._follow_redirects_for_code(
                session, location, login_url, expected_state
            )
            if code:
                return code
        elif status == 200:
            if "invalid" in body.lower() or "error" in body.lower():
                raise BrinkAuthError(
                    "Invalid username or password",
                    is_credentials_error=True,
                )

        raise BrinkAuthError("Could not extract authorization code from OIDC flow")

    async def _exchange_code_for_tokens(
        self,
        authorization_code: str,
        code_verifier: str,
    ) -> None:
        token_data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": OIDC_REDIRECT_URI,
            "client_id": OIDC_CLIENT_ID,
            "code_verifier": code_verifier,
        }

        async with async_timeout.timeout(20):
            response = await self._session.post(
                OIDC_TOKEN_URL,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if response.status != 200:
                await response.release()
                raise BrinkAuthError(
                    f"OIDC token exchange failed with status {response.status}"
                )
            payload = await response.json()
            await response.release()

        access_token = payload.get("access_token")
        if not access_token:
            raise BrinkAuthError("OIDC token response did not contain an access token")

        self._access_token = access_token
        expires_in = int(payload.get("expires_in", 3599))
        self._token_expiry = time.monotonic() + expires_in - 60
        self._refresh_token = payload.get("refresh_token")

    async def _refresh_access_token(self) -> None:
        """Refresh the bearer token if Brink issues refresh tokens."""
        if not self._refresh_token:
            raise BrinkAuthError("No refresh token available")

        token_data = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": OIDC_CLIENT_ID,
        }

        try:
            async with async_timeout.timeout(20):
                response = await self._session.post(
                    OIDC_TOKEN_URL,
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                if response.status != 200:
                    await response.release()
                    self._refresh_token = None
                    raise BrinkAuthError(
                        f"Refresh token rejected (HTTP {response.status})"
                    )
                payload = await response.json()
                await response.release()
        except (aiohttp.ClientError, asyncio.TimeoutError) as ex:
            self._refresh_token = None
            raise BrinkAuthError("Refresh token request failed") from ex

        access_token = payload.get("access_token")
        if not access_token:
            self._refresh_token = None
            raise BrinkAuthError("Refresh response missing access_token")

        self._access_token = access_token
        expires_in = int(payload.get("expires_in", 3599))
        self._token_expiry = time.monotonic() + expires_in - 60
        self._refresh_token = payload.get("refresh_token", self._refresh_token)

    async def _follow_redirects_for_code(
        self,
        session: aiohttp.ClientSession,
        redirect_url: str,
        base_url: str,
        expected_state: str,
    ) -> str | None:
        """Follow the redirect chain until the authorization code appears."""
        current_url = redirect_url
        for _ in range(10):
            if current_url.startswith("/"):
                parsed_base = urlparse(base_url)
                current_url = (
                    f"{parsed_base.scheme}://{parsed_base.netloc}{current_url}"
                )

            code = self._extract_code_from_redirect(current_url, expected_state)
            if code:
                return code

            if not self._is_trusted_url(current_url):
                return None

            try:
                async with async_timeout.timeout(15):
                    response = await session.get(current_url, allow_redirects=False)
                if response.status in (301, 302, 303, 307):
                    current_url = response.headers.get("Location", "")
                    await response.release()
                    if not current_url:
                        return None
                    continue
                final_url = str(response.url)
                await response.release()
                return self._extract_code_from_redirect(final_url, expected_state)
            except aiohttp.ClientError:
                return None

        return None

    @staticmethod
    def _extract_parameters(
        nav_items: list[dict[str, Any]],
        parameters: dict[str, dict[str, Any]],
    ) -> None:
        """Flatten parameters from all navigation items into one map."""
        for nav_item in nav_items:
            for group in nav_item.get("parameterGroups", []):
                for param in group.get("parameters", []):
                    raw_name = param.get("name", "")
                    key = PARAM_NAME_MAP.get(raw_name)
                    if key is None:
                        numeric_id = param.get("id")
                        if numeric_id is None:
                            continue
                        key = f"unknown_{numeric_id}"

                    parameters[key] = {
                        "name": TRANSLATIONS.get(raw_name, raw_name),
                        "raw_name": raw_name,
                        "value": param.get("value"),
                        "value_id": param.get("valueId"),
                        "value_state": param.get("valueState"),
                        "read_write": param.get("readWrite"),
                        "control_type": param.get("controlType"),
                        "list_items": param.get("listItems"),
                        "min_value": param.get("minValue"),
                        "max_value": param.get("maxValue"),
                        "unit_of_measure": (
                            param.get("unit") or param.get("unitOfMeasure")
                        ),
                        "component_id": param.get("componentId"),
                        "numeric_id": param.get("id"),
                        "options": BrinkHomeCloud._extract_options(
                            param.get("listItems", [])
                        ),
                    }
            BrinkHomeCloud._extract_parameters(
                nav_item.get("navigationItems", []), parameters
            )

    @staticmethod
    def _extract_options(list_items: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Normalize API list items for select/fan entities."""
        options: list[dict[str, str]] = []
        for item in list_items or []:
            if item.get("isSelectable") is False:
                continue
            value = item.get("value")
            if value is None:
                continue
            label_source = (
                item.get("translationId")
                or item.get("displayText")
                or item.get("text")
                or str(value)
            )
            options.append(
                {
                    "value": str(value),
                    "label": TRANSLATIONS.get(label_source, label_source),
                }
            )
        return options

    @staticmethod
    def _extract_form_fields(html: str) -> dict[str, str]:
        extractor = _InputFieldExtractor({"__RequestVerificationToken", "ReturnUrl"})
        extractor.feed(html)
        return extractor.results

    @staticmethod
    def _extract_code_from_redirect(url: str, expected_state: str) -> str | None:
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            returned_state = params.get("state", [expected_state])[0]
            if returned_state != expected_state:
                return None
            codes = params.get("code")
            if codes:
                return codes[0]
        except (ValueError, KeyError):
            return None
        return None

    @staticmethod
    def _generate_code_verifier() -> str:
        return secrets.token_urlsafe(48)

    @staticmethod
    def _generate_code_challenge(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    @staticmethod
    def _is_trusted_url(url: str) -> bool:
        try:
            parsed = urlparse(url)
        except ValueError:
            return False
        return (
            parsed.scheme == "https"
            and parsed.hostname == _TRUSTED_HOST
            and parsed.port in (None, 443)
        )
