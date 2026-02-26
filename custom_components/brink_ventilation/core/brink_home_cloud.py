"""Brink Home Cloud API client with dual authentication (OIDC + old portal)."""

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

from ..const import (
    API_URL,
    API_V1_URL,
    OIDC_AUTH_URL,
    OIDC_CLIENT_ID,
    OIDC_REDIRECT_URI,
    OIDC_SCOPE,
    OIDC_TOKEN_URL,
)

_LOGGER = logging.getLogger(__name__)

_OLD_API_HEADERS: dict[str, str] = {
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/json; charset=UTF-8",
}

_TRUSTED_HOST = "www.brink-home.com"


def _is_trusted_url(url: str) -> bool:
    """Return True if the URL uses HTTPS and points to the Brink Home domain."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname == _TRUSTED_HOST
        and parsed.port in (None, 443)
    )


def _extract_parameters(
    nav_item: dict[str, Any],
    parameters: dict[int, dict[str, Any]],
    _depth: int = 0,
) -> None:
    """Recursively extract parameters from a navigation item tree."""
    if _depth > 20:
        _LOGGER.warning("Maximum navigation depth reached, stopping recursion")
        return

    for group in nav_item.get("parameterGroups", []):
        for param in group.get("parameters", []):
            param_id = param.get("id")
            if param_id is not None:
                parameters[param_id] = {
                    "name": param.get("name", ""),
                    "value": param.get("value"),
                    "value_id": param.get("valueId"),
                    "value_state": param.get("valueState"),
                    "read_write": param.get("readWrite"),
                    "control_type": param.get("controlType"),
                    "list_items": param.get("listItems"),
                    "min_value": param.get("minValue"),
                    "max_value": param.get("maxValue"),
                    "unit_of_measure": param.get("unitOfMeasure"),
                    "component_id": param.get("componentId"),
                }

    for child in nav_item.get("navigationItems", []):
        _extract_parameters(child, parameters, _depth + 1)


class _InputFieldExtractor(HTMLParser):
    """Extract values from HTML <input> elements by field name."""

    def __init__(self, target_names: set[str]) -> None:
        super().__init__()
        self._targets = {n.lower() for n in target_names}
        self.results: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "input":
            return
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        name = attr_dict.get("name", "").lower()
        if name in self._targets and "value" in attr_dict:
            self.results[name] = attr_dict["value"]


class BrinkHomeCloud:
    """Interacts with Brink Home via v1.1 API (reads) and old portal API (writes)."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        old_session: aiohttp.ClientSession,
        username: str,
        password: str,
    ) -> None:
        """Initialize the Brink Home Cloud client.

        Args:
            session: HA shared session (no cookies) for v1.1 API.
            old_session: HA-managed session with CookieJar for old portal API.
            username: Brink Home portal username.
            password: Brink Home portal password.
        """
        self._session = session
        self._old_session = old_session
        self._username = username
        self._password = password

        # OIDC Bearer token state
        self._access_token: str | None = None
        self._token_expiry: float = 0.0

        # Old API cookie auth state
        self._old_api_authenticated: bool = False

        # Cache of last known good gateway map for resilience
        self._cached_gateway_map: dict[int, int] = {}

    # -------------------------------------------------------------------------
    # Public API methods
    # -------------------------------------------------------------------------

    async def login(self) -> None:
        """Perform both OIDC login (for Bearer token) and old API login (for cookies)."""
        await self._oidc_login()
        await self._old_api_login()

    async def close(self) -> None:
        """Clear sensitive state. Call on integration unload.

        Sessions are HA-managed and will be closed by HA automatically.
        """
        self._access_token = None
        self._token_expiry = 0.0
        self._old_api_authenticated = False
        self._username = ""
        self._password = ""

    async def get_systems(self) -> list[dict[str, Any]]:
        """Get list of systems by combining v1.1 API (info) and old API (gateway_id)."""
        await self._ensure_token()

        # Get systems from v1.1 API (has systemShareId, serialNumber, systemName)
        url = f"{API_V1_URL}systems?pageSize=5"
        async with asyncio.timeout(20):
            resp = await self._session.get(
                url,
                headers=self._bearer_headers(),
            )
            resp.raise_for_status()
            v1_data = await resp.json()

        _LOGGER.debug(
            "get_systems v1.1 response: %s systems found",
            v1_data.get("totalCount", 0),
        )

        # Get systems from old API (has gatewayId)
        gateway_map = await self._get_old_api_systems()

        # Update cache on successful fetch
        if gateway_map:
            self._cached_gateway_map.update(gateway_map)

        systems: list[dict[str, Any]] = []
        for item in v1_data.get("items", []):
            system_id = item.get("systemShareId")
            if system_id is None:
                _LOGGER.warning(
                    "Skipping system with missing systemShareId (keys: %s)",
                    list(item.keys()) if isinstance(item, dict) else type(item).__name__,
                )
                continue
            # Fall back to cached gateway_id if old API failed
            gw_id = gateway_map.get(system_id) or self._cached_gateway_map.get(system_id)
            systems.append(
                {
                    "system_id": system_id,
                    "gateway_id": gw_id,
                    "name": item.get("systemName", "Brink"),
                    "serial_number": item.get("serialNumber", ""),
                    "gateway_state": item.get("gatewayState"),
                }
            )

        if not systems:
            _LOGGER.warning("No systems found in Brink Home API response")

        return systems

    async def _get_old_api_systems(self) -> dict[int, int]:
        """Return a system_id -> gateway_id mapping from the old portal API."""
        await self._ensure_old_api()

        url = f"{API_URL}GetSystemList"
        try:
            async with asyncio.timeout(20):
                resp = await self._old_session.get(
                    url,
                    headers=_OLD_API_HEADERS,
                )
                if resp.status == 401:
                    _LOGGER.debug("GetSystemList got 401, re-authenticating")
                    await resp.release()
                    await self._old_api_login()
                    async with asyncio.timeout(20):
                        resp = await self._old_session.get(
                            url,
                            headers=_OLD_API_HEADERS,
                        )
                resp.raise_for_status()
                data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            _LOGGER.warning("Could not fetch gateway map from old API")
            return {}

        gateway_map: dict[int, int] = {}
        for system in data:
            sys_id = system.get("id")
            gw_id = system.get("gatewayId")
            if sys_id is not None and gw_id is not None:
                gateway_map[sys_id] = gw_id

        _LOGGER.debug("Old API gateway map: %s", gateway_map)
        return gateway_map

    async def get_device_data(self, system_id: int) -> dict[str, Any]:
        """Get all parameters for a system from the v1.1 uidescription endpoint."""
        if not isinstance(system_id, int):
            raise ValueError(
                f"system_id must be an integer, got {type(system_id).__name__}"
            )

        await self._ensure_token()

        url = f"{API_V1_URL}systems/{system_id}/uidescription"
        async with asyncio.timeout(20):
            resp = await self._session.get(
                url,
                headers=self._bearer_headers(),
            )
            resp.raise_for_status()
            data = await resp.json()

        _LOGGER.debug("get_device_data for system %s received", system_id)

        return self._parse_uidescription(data)

    async def write_parameters(
        self,
        system_id: int,
        gateway_id: int,
        params: list[tuple[int, str]],
    ) -> None:
        """Write multiple parameter values in one bundle via the old portal API."""
        if not isinstance(system_id, int) or not isinstance(gateway_id, int):
            raise ValueError("system_id and gateway_id must be integers")

        await self._ensure_old_api()

        write_values: list[dict[str, Any]] = []
        for vid, val in params:
            if not isinstance(vid, int):
                raise ValueError(
                    f"value_id must be an integer, got {type(vid).__name__}"
                )
            write_values.append({"ValueId": vid, "Value": val})

        payload: dict[str, Any] = {
            "GatewayId": gateway_id,
            "SystemId": system_id,
            "WriteParameterValues": write_values,
            "SendInOneBundle": True,
            "DependendReadValuesAfterWrite": [],
        }

        url = f"{API_URL}WriteParameterValuesAsync"
        _LOGGER.debug("Writing parameters to system %s: %s", system_id, params)

        for attempt in range(2):
            async with asyncio.timeout(20):
                resp = await self._old_session.post(
                    url,
                    json=payload,
                    headers=_OLD_API_HEADERS,
                )

            if resp.status == 401:
                await resp.release()
                if attempt == 0:
                    _LOGGER.debug("Write got 401, re-authenticating old API")
                    await self._old_api_login()
                    continue
                raise BrinkAuthError("Write failed: persistent 401 after re-auth")

            try:
                resp.raise_for_status()
                await resp.read()
            finally:
                await resp.release()
            return

    # -------------------------------------------------------------------------
    # OIDC PKCE Authentication
    # -------------------------------------------------------------------------

    async def _oidc_login(self) -> None:
        """Perform OIDC Authorization Code + PKCE flow to get a Bearer token."""
        code_verifier = self._generate_code_verifier()
        code_challenge = self._generate_code_challenge(code_verifier)
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)

        jar = aiohttp.CookieJar(unsafe=False)
        async with aiohttp.ClientSession(cookie_jar=jar) as oidc_session:
            # Step 1: GET authorize endpoint
            auth_params: dict[str, str] = {
                "client_id": OIDC_CLIENT_ID,
                "redirect_uri": OIDC_REDIRECT_URI,
                "response_type": "code",
                "scope": OIDC_SCOPE,
                "state": state,
                "nonce": nonce,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }

            # allow_redirects=True is safe here: this is a fresh session with no
            # sensitive cookies yet.  The final URL is validated below.
            _LOGGER.debug("Starting OIDC authorize request")
            async with asyncio.timeout(30):
                auth_resp = await oidc_session.get(
                    OIDC_AUTH_URL,
                    params=auth_params,
                    allow_redirects=True,
                )

            if auth_resp.status != 200:
                raise BrinkAuthError(
                    f"OIDC authorize failed with status {auth_resp.status}"
                )

            login_page_html = await auth_resp.text()
            login_url = str(auth_resp.url)

            # Validate that the login form URL is on the trusted domain
            if not _is_trusted_url(login_url):
                raise BrinkAuthError(
                    f"OIDC login page redirected to untrusted host: "
                    f"{urlparse(login_url).hostname}"
                )

            # Step 2: Parse CSRF token and ReturnUrl from login form
            form_fields = self._extract_form_fields(login_page_html)
            csrf_token = form_fields.get("__requestverificationtoken")
            if not csrf_token:
                raise BrinkAuthError(
                    "Could not find CSRF token in OIDC login page"
                )

            return_url = form_fields.get("returnurl")

            # Step 3: POST login form
            form_data: dict[str, str] = {
                "Username": self._username,
                "Password": self._password,
                "__RequestVerificationToken": csrf_token,
            }
            if return_url:
                if return_url.startswith("/") and not return_url.startswith("//"):
                    # Relative path — safe
                    form_data["ReturnUrl"] = return_url
                elif _is_trusted_url(return_url):
                    # Absolute URL on trusted domain
                    form_data["ReturnUrl"] = return_url
                else:
                    _LOGGER.warning(
                        "Ignoring untrusted ReturnUrl hostname"
                    )

            _LOGGER.debug("Posting OIDC login form")
            async with asyncio.timeout(30):
                login_resp = await oidc_session.post(
                    login_url,
                    data=form_data,
                    allow_redirects=False,
                )

            authorization_code: str | None = None

            if login_resp.status in (301, 302, 303, 307):
                redirect_location = login_resp.headers.get("Location", "")
                await login_resp.release()
                authorization_code = self._extract_code_from_redirect(
                    redirect_location, expected_state=state
                )

                if not authorization_code:
                    _LOGGER.debug(
                        "Following redirect chain to get auth code"
                    )
                    authorization_code = await self._follow_redirects_for_code(
                        oidc_session, redirect_location, login_url, state
                    )
            elif login_resp.status == 200:
                body = await login_resp.text()
                if "invalid" in body.lower() or "error" in body.lower():
                    raise BrinkAuthError("Invalid username or password")
                raise BrinkAuthError(
                    "OIDC login returned 200 - credentials may be invalid"
                )
            else:
                raise BrinkAuthError(
                    f"OIDC login failed with status {login_resp.status}"
                )

            if not authorization_code:
                raise BrinkAuthError(
                    "Could not extract authorization code from OIDC flow"
                )

            _LOGGER.debug("Got authorization code, exchanging for token")

        # Step 4: Exchange authorization code for token
        token_data: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": OIDC_REDIRECT_URI,
            "client_id": OIDC_CLIENT_ID,
            "code_verifier": code_verifier,
        }

        async with asyncio.timeout(20):
            token_resp = await self._session.post(
                OIDC_TOKEN_URL,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if token_resp.status != 200:
            await token_resp.release()
            _LOGGER.error(
                "Token exchange failed with HTTP %s", token_resp.status
            )
            raise BrinkAuthError(
                f"OIDC token exchange failed with status {token_resp.status}"
            )

        token_json = await token_resp.json()
        access_token = token_json.get("access_token")
        if not access_token:
            _LOGGER.error("Token response did not contain expected fields")
            raise BrinkAuthError(
                "OIDC token response did not contain an access token"
            )
        self._access_token = access_token
        expires_in: int = token_json.get("expires_in", 3599)
        self._token_expiry = time.monotonic() + expires_in - 60

        _LOGGER.debug(
            "OIDC token obtained, expires in %s seconds", expires_in
        )

    async def _follow_redirects_for_code(
        self,
        session: aiohttp.ClientSession,
        redirect_url: str,
        base_url: str,
        expected_state: str | None = None,
    ) -> str | None:
        """Follow redirect chain to extract the authorization code.

        Only follows redirects that stay on the trusted Brink Home domain
        (HTTPS) to prevent leaking the authorization code to a hostile server.
        """
        max_redirects = 10
        current_url = redirect_url

        for _ in range(max_redirects):
            if current_url.startswith("/"):
                parsed_base = urlparse(base_url)
                current_url = (
                    f"{parsed_base.scheme}://{parsed_base.netloc}{current_url}"
                )

            code = self._extract_code_from_redirect(
                current_url, expected_state=expected_state
            )
            if code:
                return code

            if not _is_trusted_url(current_url):
                _LOGGER.warning(
                    "Refusing to follow redirect to untrusted URL: %s",
                    urlparse(current_url).hostname,
                )
                break

            try:
                async with asyncio.timeout(15):
                    resp = await session.get(
                        current_url, allow_redirects=False
                    )

                if resp.status in (301, 302, 303, 307):
                    current_url = resp.headers.get("Location", "")
                    await resp.release()
                    if not current_url:
                        break
                else:
                    resp_url = str(resp.url)
                    await resp.release()
                    final_code = self._extract_code_from_redirect(
                        resp_url, expected_state=expected_state
                    )
                    if final_code:
                        return final_code
                    break
            except (aiohttp.ClientError, asyncio.TimeoutError):
                _LOGGER.debug("Error following redirect")
                break

        return None

    # -------------------------------------------------------------------------
    # Old Portal API Authentication
    # -------------------------------------------------------------------------

    async def _ensure_old_api(self) -> None:
        """Ensure the old API session is authenticated."""
        if not self._old_api_authenticated:
            await self._old_api_login()

    async def _old_api_login(self) -> None:
        """Authenticate with the old portal API to get session cookies for writes."""
        data: dict[str, str] = {
            "UserName": self._username,
            "Password": self._password,
        }
        url = f"{API_URL}UserLogon"

        _LOGGER.debug("Logging into old portal API")

        try:
            async with asyncio.timeout(20):
                resp = await self._old_session.post(
                    url,
                    json=data,
                    headers=_OLD_API_HEADERS,
                )
                resp.raise_for_status()
                await resp.read()  # consume body
        except aiohttp.ClientResponseError as ex:
            self._old_api_authenticated = False
            if ex.status in (401, 403):
                raise BrinkAuthError(
                    f"Old API login failed (HTTP {ex.status})"
                ) from ex
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError):
            self._old_api_authenticated = False
            raise

        self._old_api_authenticated = True
        _LOGGER.debug("Old portal API login successful")

    # -------------------------------------------------------------------------
    # Token management
    # -------------------------------------------------------------------------

    async def _ensure_token(self) -> None:
        """Ensure we have a valid Bearer token, re-authenticating if needed."""
        if self._access_token and time.monotonic() < self._token_expiry:
            return

        _LOGGER.debug("Bearer token expired or missing, re-authenticating")
        await self._oidc_login()

    def _bearer_headers(self) -> dict[str, str]:
        """Return headers with Bearer token for v1.1 API calls."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }

    # -------------------------------------------------------------------------
    # Parsing helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_uidescription(data: dict[str, Any]) -> dict[str, Any]:
        """Parse the v1.1 uidescription response into components with parameters."""
        nav_items = data.get("root", {}).get("navigationItems", [])

        components: list[dict[str, Any]] = []
        for nav_item in nav_items:
            parameters: dict[int, dict[str, Any]] = {}
            _extract_parameters(nav_item, parameters)

            if parameters:
                components.append(
                    {
                        "component_id": nav_item.get("componentId"),
                        "name": nav_item.get("name", "Unknown"),
                        "parameters": parameters,
                    }
                )

        return {"components": components}

    @staticmethod
    def _extract_form_fields(html: str) -> dict[str, str]:
        """Extract input field values from login form HTML.

        Uses stdlib html.parser for resilience against HTML reformatting.
        """
        extractor = _InputFieldExtractor(
            {"__RequestVerificationToken", "ReturnUrl"}
        )
        extractor.feed(html)
        return extractor.results

    @staticmethod
    def _extract_code_from_redirect(
        url: str, expected_state: str | None = None
    ) -> str | None:
        """Extract authorization code from redirect URL query string.

        If expected_state is provided, validates the state parameter to
        prevent CSRF attacks on the OAuth redirect.
        """
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            if expected_state is not None:
                returned_states = params.get("state")
                if not returned_states or returned_states[0] != expected_state:
                    _LOGGER.warning("OAuth state mismatch — possible CSRF attack")
                    return None

            codes = params.get("code")
            if codes:
                return codes[0]
            if parsed.fragment:
                frag_params = parse_qs(parsed.fragment)
                codes = frag_params.get("code")
                if codes:
                    return codes[0]
        except (ValueError, KeyError):
            _LOGGER.debug("Error parsing redirect URL for authorization code")

        return None

    @staticmethod
    def _generate_code_verifier() -> str:
        """Generate a PKCE code_verifier (43-128 chars, URL-safe)."""
        return secrets.token_urlsafe(48)

    @staticmethod
    def _generate_code_challenge(verifier: str) -> str:
        """Generate a PKCE S256 code_challenge from the verifier."""
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class BrinkAuthError(Exception):
    """Raised when Brink Home authentication fails."""
