"""Brink Home Cloud API client using the v1.1 API with OIDC PKCE auth."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

import async_timeout
from aiohttp import (
    ClientConnectionError,
    ClientConnectorError,
    ClientError,
    ClientResponse,
    ClientResponseError,
    ClientSession,
    ClientTimeout,
    CookieJar,
    ServerDisconnectedError,
)

from ..const import (
    API_V1_URL,
    CONTROL_TYPE_MAP,
    OIDC_AUTH_URL,
    OIDC_CLIENT_ID,
    OIDC_REDIRECT_URI,
    OIDC_SCOPE,
    OIDC_TOKEN_URL,
    PARAM_NAME_MAP,
    PARAMETER_NAMES,
    VALUE_STATE_MAP,
    WRITE_VALUE_STATE,
)
from ..models import BrinkAlert, BrinkAlertLevel, BrinkSettings, BrinkSystem, BrinkUser
from ..translations import TRANSLATIONS
from .option_mapping import build_option_state_map

_LOGGER = logging.getLogger(__name__)
_TRUSTED_HOST = "www.brink-home.com"
_ALERT_PAGE_SIZE = 10
_MAX_ALERT_PAGES = 100


class BrinkApiError(Exception):
    """Represent a Brink API error."""

    def __init__(
        self,
        message: str,
        *,
        error_code: int | None = None,
        error_type: str = "api",
    ) -> None:
        """Initialize the Brink API error."""
        super().__init__(message)
        self.error_code = error_code
        self.error_type = error_type


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


class BrinkClient:
    """Base class for Brink Home API clients."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session


@dataclass(slots=True, frozen=True)
class BrinkOidcConfig:
    """Brink OIDC configuration."""

    authority: str
    client_id: str
    response_type: str
    scope: str
    redirect_url: str


OIDC_CONFIG = BrinkOidcConfig(
    authority="https://www.brink-home.com/idsrv",
    client_id="spa",
    response_type="code",
    scope="openid api role locale",
    redirect_url="https://www.brink-home.com/app/",
)


class BrinkHomeCloud:
    """Interact with Brink Home through the v1.1 API."""

    _OBSERVED_VALUE_STATES: set[int] = set()
    _OBSERVED_CONTROL_TYPES: set[int] = set()
    _OBSERVED_HINTS: set[int] = set()

    def __init__(self, session: ClientSession, username: str, password: str):
        self.api_is_online: bool = False
        self.api_error: str | None = None
        self.api_error_code: int | None = None
        self.api_error_type: str | None = None
        self._session = session
        self._username = username
        self._password = password
        self._timeout = 30
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

    async def async_get_user(self) -> BrinkUser:
        """Return the authenticated Brink user."""

        response = await self._api_request(
            "GET",
            f"{API_V1_URL}user",
        )

        async with response:
            payload = cast(dict[str, object], await response.json())


        return payload

    async def async_update_user_general(
        self,
        mail_address_id: int,
        user_role_id: int,
        culture_info_code: str,
    ) -> dict[str, object]:
        """Update the authenticated user's general settings."""

        response = await self._api_request(
            "PUT",
            f"{API_V1_URL}user/general",
            json_data={
                "mailAddressId": mail_address_id,
                "userRoleId": user_role_id,
                "cultureInfoCode": culture_info_code,
            },
        )

        async with response:
            payload = cast(dict[str, object], await response.json())


        return payload

    async def async_get_alerts(
        self,
        system_id: int,
        *,
        page_index: int = 0,
    ) -> dict[str, object]:
        """Return one unarchived-alert page, rejecting invalid pagination input."""
        if (
            not isinstance(page_index, int)
            or isinstance(page_index, bool)
            or page_index < 0
        ):
            raise ValueError("Alert page_index must be a non-negative integer")

        response = await self._api_request(
            "GET",
            f"{API_V1_URL}systems/{system_id}/alerts/criterion",
            params={
                "pageIndex": page_index,
                "pageSize": _ALERT_PAGE_SIZE,
                "sortColumn": "level",
                "sortDirection": 2,
                "filterSpecs[0].fieldName": "isArchived",
                "filterSpecs[0].value": "false",
            },
        )

        async with response:
            payload = await response.json()

        if not isinstance(payload, dict):
            raise BrinkApiError(
                "Brink returned an invalid alert response object",
                error_type="invalid_response",
            )

        return payload

    async def async_get_active_alerts(
        self,
        system_id: int,
    ) -> list[BrinkAlert]:
        """Return all active alerts or fail without publishing a partial count."""
        alerts: list[BrinkAlert] = []
        seen_alert_ids: set[int] = set()
        fetched_items = 0
        expected_total: int | None = None

        for page_index in range(_MAX_ALERT_PAGES):
            data = await self.async_get_alerts(system_id, page_index=page_index)
            items = data.get("items")
            total_count = data.get("totalCount")

            if not isinstance(items, list):
                raise BrinkApiError(
                    "Brink returned an invalid alert list",
                    error_type="invalid_response",
                )

            if total_count is not None and (
                not isinstance(total_count, int)
                or isinstance(total_count, bool)
                or total_count < 0
            ):
                raise BrinkApiError(
                    "Brink returned an invalid alert total count",
                    error_type="invalid_response",
                )

            if total_count is not None:
                if expected_total is not None and expected_total != total_count:
                    raise BrinkApiError(
                        "Brink changed the alert total while fetching alert pages",
                        error_type="invalid_response",
                    )
                expected_total = total_count

            for item in items:
                if not isinstance(item, dict) or (
                    not isinstance(item.get("id"), int)
                    or isinstance(item["id"], bool)
                    or item["id"] < 0
                    or not isinstance(item.get("isActive"), bool)
                    or not isinstance(item.get("isArchived"), bool)
                ):
                    raise BrinkApiError(
                        "Brink returned an invalid alert record",
                        error_type="invalid_response",
                    )

                alert_id = item["id"]
                if alert_id in seen_alert_ids:
                    raise BrinkApiError(
                        "Brink repeated an alert while fetching alert pages",
                        error_type="invalid_response",
                    )
                seen_alert_ids.add(alert_id)

                if not item["isActive"] or item["isArchived"]:
                    continue

                try:
                    alerts.append(self._parse_alert(item))
                except (KeyError, TypeError, ValueError, OverflowError):
                    raise BrinkApiError(
                        "Brink returned invalid active alert details",
                        error_type="invalid_response",
                    ) from None

            fetched_items += len(items)
            if expected_total is not None:
                if fetched_items > expected_total or (
                    not items and fetched_items < expected_total
                ):
                    raise BrinkApiError(
                        "Brink returned inconsistent alert pagination",
                        error_type="invalid_response",
                    )
                if fetched_items == expected_total:
                    return alerts
            elif len(items) < _ALERT_PAGE_SIZE:
                return alerts

        raise BrinkApiError(
            "Brink alert pagination exceeded the safe request limit",
            error_type="invalid_response",
        )

    @staticmethod
    def _parse_alert(item: dict[str, object]) -> BrinkAlert:
        """Parse a Brink alert."""

        outgoing = item.get("outgoing")

        return BrinkAlert(
            id=int(item["id"]),
            component_id=int(item["componentId"]),
            code=int(item["code"]),
            level=BrinkAlertLevel(int(item["level"])),
            is_active=bool(item["isActive"]),
            is_archived=bool(item["isArchived"]),
            incoming=datetime.fromisoformat(
                str(item["incoming"])
            ),
            outgoing=(
                datetime.fromisoformat(str(outgoing))
                if outgoing
                else None
            ),
            code_text=item.get("codeTextId"),
            description=item.get("codeDescriptionTextId"),
        )

    async def get_systems(self) -> list[BrinkSystem]:
        """Return the systems visible to the current account."""
        response = await self._api_request(
            "GET",
            f"{API_V1_URL}systems?pageSize=5",
        )

        try:
            payload = await response.json()
        finally:
            await response.release()


        items = payload.get("items")
        if not isinstance(items, list):
            return []

        systems: list[dict[str, object]] = []

        for item in items:
            if not isinstance(item, dict):
                continue

            system_id = item.get("systemShareId")
            if system_id is None:
                continue

            raw_alert_count = item.get("activeAlertCount")
            if isinstance(raw_alert_count, dict):
                raw_alert_count = raw_alert_count.get("alertCount")

            normalized_alert_count = (
                raw_alert_count
                if isinstance(raw_alert_count, int)
                and not isinstance(raw_alert_count, bool)
                and raw_alert_count >= 0
                else None
            )

            system: dict[str, object] = {
                "name": item.get("systemName") or "Brink",
                "serial_number": item.get("serialNumber"),
                "system_id": system_id,
                "is_system_owner": item.get("isSystemOwner"),
                "is_editable": item.get("isEditable"),
                "access_level": item.get("accessLevel"),
                "owner_group_name": item.get("ownerGroupName"),
                "is_favorite": item.get("isFavorite"),
                "gateway_state": item.get("gatewayState"),
                "active_alert_count": normalized_alert_count,
                "iana_time_zone": item.get("ianaTimeZone"),
                "two_letter_country_code": item.get("twoLetterCountryCode"),
                "user_group_names": item.get("userGroupNames"),
                "total_count": item.get("totalCount"),
            }

            systems.append(system)


        return systems

    async def async_get_device(self, system_id: int) -> dict[str, dict[str, object]]:
        """Return a flattened parameter map for a system."""
        response = await self._api_request(
            "GET", f"{API_V1_URL}systems/{system_id}"
        )
        try:
            payload = await response.json()
        finally:
            await response.release()

        return payload

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

    async def async_get_settings(self) -> BrinkSettings:
        """Return Brink portal settings."""

        response = await self._api_request(
            "GET",
            f"{API_V1_URL}settings",
        )

        async with response:
            payload = cast(dict[str, object], await response.json())


        return payload

    async def async_get_translations(
        self,
        language: str = "en",
        *,
        translation_format: int = 2,
        version: str = "2.4.3",
    ) -> dict[str, str]:
        """Return Brink translations."""

        response = await self._api_request(
            "GET",
            f"{API_V1_URL}settings/languages/{language}",
            params={
                "translationFormat": translation_format,
                "v": version,
            },
        )

        async with response:
            payload = await response.json()

        return cast(dict[str, str], payload)

    async def _api_request(
        self,
        method: str,
        url: str,
        *,
        json_data: dict[str, object] | None = None,
        params: dict[str, object] | None = None,
    ) -> ClientResponse:
        """Perform an authenticated v1.1 API request."""
        max_attempts = 3

        _LOGGER.debug("Brink request method=%s timeout=%s", method, self._timeout)

        for attempt in range(max_attempts):
            await self._ensure_token()

            try:
                response = await self._session.request(
                    method,
                    url,
                    json=json_data,
                    params=params,
                    timeout=ClientTimeout(total=self._timeout),
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Accept": "application/json",
                    },
                )

                if response.status == 401:
                    await response.release()

                    if attempt == 0:
                        async with self._token_lock:
                            self._token_expiry = 0.0
                            self._access_token = None
                        continue

                    self.api_is_online = False
                    self.api_error_code = 401
                    self.api_error_type = "http"
                    self.api_error = "HTTP 401: Authentication failed"

                    raise BrinkAuthError(
                        "Authentication failed after retry"
                    )

                try:
                    response.raise_for_status()
                except ClientResponseError as err:
                    await response.release()

                    raise BrinkApiError(
                        f"HTTP {err.status}: HTTP request failed",
                        error_code=err.status,
                        error_type="http",
                    ) from err

                # The complete HTTP request was successful.
                self.api_is_online = True
                self.api_error = None
                self.api_error_code = None
                self.api_error_type = None

                return response

            except ClientConnectorError as err:
                self.api_is_online = False
                self.api_error = "Brink API connection failed"
                self.api_error_code = None
                self.api_error_type = "connection"

                _LOGGER.warning("Brink connection/DNS failure: %s", type(err).__name__)

                raise BrinkApiError(
                    "Unable to connect to Brink API"
                ) from err

            except (
                ClientConnectionError,
                ServerDisconnectedError,
                TimeoutError,
            ) as err:
                if attempt < max_attempts - 1:
                    _LOGGER.debug(
                        "Brink request failed (%s/%s): method=%s error_type=%s",
                        attempt + 1,
                        max_attempts,
                        method,
                        type(err).__name__,
                    )
                else:
                    _LOGGER.warning(
                        "Brink request failed (%s/%s): method=%s error_type=%s",
                        attempt + 1,
                        max_attempts,
                        method,
                        type(err).__name__,
                    )

                if attempt == max_attempts - 1:
                    self.api_is_online = False
                    self.api_error = "Brink API connection failed"
                    self.api_error_code = None
                    self.api_error_type = "connection"

                    raise BrinkApiError(
                        f"Brink request failed after {max_attempts} attempts"
                    ) from err

                await asyncio.sleep(2)

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

        jar = CookieJar(unsafe=False)
        async with ClientSession(cookie_jar=jar) as oidc_session:
            login_url, csrf_token, return_url = await self._fetch_login_page(
                oidc_session, code_challenge, state, nonce
            )
            authorization_code = await self._submit_login_credentials(
                oidc_session, login_url, csrf_token, return_url, state
            )

        await self._exchange_code_for_tokens(authorization_code, code_verifier)

    async def _fetch_login_page(
        self,
        session: ClientSession,
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
        session: ClientSession,
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
        if return_url and return_url.startswith("/") and not return_url.startswith("//") or self._is_trusted_url(return_url):
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

        async with async_timeout.timeout(30):
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
                # _LOGGER.debug("Brink Flair refresh access token payload: %s", payload)
                await response.release()
        except (ClientError, asyncio.TimeoutError) as ex:
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

        _LOGGER.debug(
            "Brink token refreshed successfully: expires_in=%s refresh_token=%s",
            expires_in,
            bool(self._refresh_token),
        )

    async def _follow_redirects_for_code(
        self,
        session: ClientSession,
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
            except ClientError:
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
                    numeric_id = param.get("id")

                    key = PARAM_NAME_MAP.get(raw_name)

                    if key is None and numeric_id is not None:
                        key = PARAMETER_NAMES.get(numeric_id)

                    if key is None:
                        if numeric_id is None:
                            continue
                        key = f"unknown_{numeric_id}"

                    if key.startswith("unknown_"):
                        _LOGGER.debug("Unmapped Brink parameter encountered")

                    list_items = param.get("listItems") or []

                    options = (
                        BrinkHomeCloud._extract_options(list_items)
                        if list_items
                        else []
                    )
                    options_map: dict[str, str] = {}
                    reverse_options_map: dict[str, str] = {}
                    for opt in options:
                        val = opt["value"]
                        lbl = opt["label"]
                        if val not in options_map:
                            options_map[val] = lbl
                        if lbl not in reverse_options_map:
                            reverse_options_map[lbl] = val

                    option_state_map, ambiguous_option_states = build_option_state_map(
                        (option["value"], option["label"]) for option in options
                    )

                    # if options:
                    #    """Show parameter with options"""
                    #    _LOGGER.debug(
                    #        "Parameter %s (%s) current_value=%s options=%s read_write=%s "
                    #        "min=%s max=%s step_width=%s decimals=%s "
                    #        "nr_options=%s",
                    #        key,
                    #        numeric_id,
                    #        param.get("value"),
                    #        options,
                    #        param.get("readWrite"),
                    #        param.get("minValue"),
                    #        param.get("maxValue"),
                    #        param.get("stepWidth"),
                    #        param.get("decimals"),
                    #        len(options),
                    #    )

                    value_state = param.get("valueState")

                    # if value_state not in (None, 0):
                    #    """Show valid values"""
                    #    _LOGGER.info(
                    #        "Parameter: %s (%s) valueState=%s value=%s",
                    #        key,
                    #        numeric_id,
                    #        value_state,
                    #        param.get("value"),
                    #    )

                    if isinstance(value_state, int) and value_state not in BrinkHomeCloud._OBSERVED_VALUE_STATES:
                        BrinkHomeCloud._OBSERVED_VALUE_STATES.add(value_state)

                        _LOGGER.info(
                            "Discovered valueState=%s (%s) parameter=%s (%s)",
                            value_state,
                            VALUE_STATE_MAP.get(value_state, "unknown"),
                            key,
                            numeric_id,
                        )

#                    if value_state != 0:
#                        _LOGGER.info(
#                            "Parameter !=0: %s (%s) value=%s valueState=%s readWrite=%s controlType=%s",
#                            key,
#                            numeric_id,
#                            param.get("value"),
#                            value_state,
#                            param.get("readWrite"),
#                            param.get("controlType"),
#                        )

                    control_type = param.get("controlType")

                    if isinstance(control_type, int):
                        if control_type not in BrinkHomeCloud._OBSERVED_CONTROL_TYPES:
                            BrinkHomeCloud._OBSERVED_CONTROL_TYPES.add(control_type)

                            _LOGGER.info(
                                "Discovered controlType=%s (%s) parameter=%s (%s)",
                                control_type,
                                CONTROL_TYPE_MAP.get(control_type, "unknown"),
                                key,
                                numeric_id,
                            )

                    hints = param.get("hints")

                    if isinstance(hints, int):
                        if hints not in BrinkHomeCloud._OBSERVED_HINTS:
                            BrinkHomeCloud._OBSERVED_HINTS.add(hints)

                            _LOGGER.info(
                                "Discovered hints=%s parameter=%s (%s) controlType=%s",
                                hints,
                                key,
                                numeric_id,
                                param.get("controlType"),
                            )

                    parameters[key] = {
                        "name": TRANSLATIONS.get(raw_name, raw_name),
                        "raw_name": raw_name,
                        "value": param.get("value"),
                        "value_id": param.get("valueId"),
                        "value_state": param.get("valueState"),
                        "read_write": param.get("readWrite"),
                        "control_type": param.get("controlType"),
                        "list_items": list_items,
                        "min_value": param.get("minValue"),
                        "max_value": param.get("maxValue"),
                        "default_value": param.get("defaultValue"),
                        "step_width": param.get("stepWidth"),
                        "decimals": param.get("decimals"),
                        "unit_of_measure": param.get("unit"),
                        "component_id": param.get("componentId"),
                        "numeric_id": numeric_id,
                        "options": options,
                        "options_map": options_map,
                        "reverse_options_map": reverse_options_map,
                        "option_state_map": option_state_map,
                        "ambiguous_option_states": ambiguous_option_states,
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
        # _LOGGER.debug("Brink Flair options: %s", options)
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


"""
ENDPOINTS = {
    "settings": f"{API_V1_URL}settings",
GET    user
PUT    user/general
PATCH  user/password
PUT    user/expert-role
GET    user/edit-form
GET    user/expert-role/edit-form
DELETE user
POST   systems
GET    systems/{id}
GET    systems/{id}/properties
PATCH  systems/{id}/unlock
GET    systems/{id}/unlock-form
GET    systems/{id}/changelogs/description
GET    systems/{id}/alerts
GET    systems/{id}/firmware
GET    settings/gateway/master-data-descriptions
}
"""
