"""Brink Home Cloud API client with dual authentication (OIDC + old portal)."""
import asyncio
import base64
import hashlib
import logging
import re
import secrets
import time
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

_OLD_API_HEADERS = {
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
    return parsed.scheme == "https" and parsed.hostname == _TRUSTED_HOST


def _extract_parameters(nav_item: dict, parameters: dict, _depth: int = 0) -> None:
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


class BrinkHomeCloud:
    """Interacts with Brink Home via v1.1 API (reads) and old portal API (writes)."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
    ):
        """Initialize the Brink Home Cloud client."""
        self._session = session
        self._username = username
        self._password = password

        # OIDC Bearer token state
        self._access_token: str | None = None
        self._token_expiry: float = 0.0

        # Old API uses cookie-based auth and needs its own session
        # (HA's shared session uses DummyCookieJar which discards cookies)
        self._old_session: aiohttp.ClientSession | None = None
        self._old_api_authenticated = False

    # -------------------------------------------------------------------------
    # Public API methods
    # -------------------------------------------------------------------------

    async def login(self) -> None:
        """Perform both OIDC login (for Bearer token) and old API login (for cookies)."""
        await self._oidc_login()
        await self._old_api_login()

    async def close(self) -> None:
        """Close sessions and clear sensitive state. Call on integration unload."""
        if self._old_session and not self._old_session.closed:
            await self._old_session.close()
            self._old_session = None

        # Clear sensitive credentials from memory
        self._access_token = None
        self._token_expiry = 0.0
        self._old_api_authenticated = False

    async def get_systems(self) -> list[dict]:
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

        systems = []
        for item in v1_data.get("items", []):
            system_id = item.get("systemShareId")
            if system_id is None:
                _LOGGER.warning(
                    "Skipping system with missing systemShareId (keys: %s)",
                    list(item.keys()) if isinstance(item, dict) else type(item).__name__,
                )
                continue
            systems.append(
                {
                    "system_id": system_id,
                    "gateway_id": gateway_map.get(system_id),
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
        await self._ensure_old_session()

        url = f"{API_URL}GetSystemList"
        try:
            async with asyncio.timeout(20):
                resp = await self._old_session.get(
                    url,
                    headers=_OLD_API_HEADERS,
                )
                if resp.status == 401:
                    _LOGGER.debug("GetSystemList got 401, re-authenticating")
                    await self._old_api_login()
                    resp = await self._old_session.get(
                        url,
                        headers=_OLD_API_HEADERS,
                    )
                resp.raise_for_status()
                data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            _LOGGER.warning("Could not fetch gateway map from old API")
            return {}

        gateway_map = {}
        for system in data:
            sys_id = system.get("id")
            gw_id = system.get("gatewayId")
            if sys_id is not None and gw_id is not None:
                gateway_map[sys_id] = gw_id

        _LOGGER.debug("Old API gateway map: %s", gateway_map)
        return gateway_map

    async def get_device_data(self, system_id: int) -> dict:
        """Get all parameters for a system from the v1.1 uidescription endpoint."""
        # Validate system_id is an integer to prevent URL path injection
        if not isinstance(system_id, int):
            raise ValueError(f"system_id must be an integer, got {type(system_id).__name__}")

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

    async def write_parameter(
        self, system_id: int, gateway_id: int, value_id: int, value: str
    ) -> None:
        """Write a single parameter value via the old portal API."""
        await self.write_parameters(system_id, gateway_id, [(value_id, value)])

    async def write_parameters(
        self,
        system_id: int,
        gateway_id: int,
        params: list[tuple[int, str]],
    ) -> None:
        """Write multiple parameter values in one bundle via the old portal API."""
        # Validate IDs are integers to prevent injection in JSON payload
        if not isinstance(system_id, int) or not isinstance(gateway_id, int):
            raise ValueError("system_id and gateway_id must be integers")

        await self._ensure_old_session()

        write_values = []
        for vid, val in params:
            if not isinstance(vid, int):
                raise ValueError(
                    f"value_id must be an integer, got {type(vid).__name__}"
                )
            write_values.append({"ValueId": vid, "Value": val})

        payload = {
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

            if resp.status == 401 and attempt == 0:
                _LOGGER.debug("Write got 401, re-authenticating old API")
                await self._old_api_login()
                continue

            resp.raise_for_status()
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

        jar = aiohttp.CookieJar(unsafe=True)
        async with aiohttp.ClientSession(cookie_jar=jar) as oidc_session:
            # Step 1: GET authorize endpoint
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
            # to prevent posting credentials to a hostile redirect target
            if not _is_trusted_url(login_url):
                raise BrinkAuthError(
                    f"OIDC login page redirected to untrusted host: "
                    f"{urlparse(login_url).hostname}"
                )

            # Step 2: Parse CSRF token and ReturnUrl from login form
            csrf_token = self._parse_csrf_token(login_page_html)
            if not csrf_token:
                raise BrinkAuthError(
                    "Could not find CSRF token in OIDC login page"
                )

            return_url = self._parse_return_url(login_page_html)

            # Step 3: POST login form
            form_data = {
                "Username": self._username,
                "Password": self._password,
                "__RequestVerificationToken": csrf_token,
            }
            if return_url:
                parsed_return = urlparse(return_url)
                if parsed_return.scheme in ("", "https") and (
                    not parsed_return.hostname
                    or parsed_return.hostname == _TRUSTED_HOST
                ):
                    form_data["ReturnUrl"] = return_url
                else:
                    _LOGGER.warning(
                        "Ignoring untrusted ReturnUrl: %s",
                        parsed_return.hostname,
                    )

            _LOGGER.debug(
                "Posting OIDC login form for user %s", self._username
            )
            async with asyncio.timeout(30):
                login_resp = await oidc_session.post(
                    login_url,
                    data=form_data,
                    allow_redirects=False,
                )

            authorization_code = None

            if login_resp.status in (301, 302, 303, 307):
                redirect_location = login_resp.headers.get("Location", "")
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
        token_data = {
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
            _LOGGER.error(
                "Token exchange failed with HTTP %s", token_resp.status
            )
            raise BrinkAuthError(
                f"OIDC token exchange failed with status {token_resp.status}"
            )

        token_json = await token_resp.json()
        access_token = token_json.get("access_token")
        if not access_token:
            _LOGGER.error(
                "Token response missing access_token: %s",
                list(token_json.keys()),
            )
            raise BrinkAuthError(
                "OIDC token response did not contain an access token"
            )
        self._access_token = access_token
        expires_in = token_json.get("expires_in", 3599)
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
        Relative paths are resolved against the base URL.
        """
        max_redirects = 10
        current_url = redirect_url

        for _ in range(max_redirects):
            if current_url.startswith("/"):
                parsed_base = urlparse(base_url)
                current_url = (
                    f"{parsed_base.scheme}://{parsed_base.netloc}{current_url}"
                )

            # Check for auth code before making a request
            code = self._extract_code_from_redirect(
                current_url, expected_state=expected_state
            )
            if code:
                return code

            # Only follow redirects to the trusted Brink domain over HTTPS
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
                    if not current_url:
                        break
                else:
                    final_code = self._extract_code_from_redirect(
                        str(resp.url), expected_state=expected_state
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

    async def _ensure_old_session(self) -> None:
        """Ensure the old API session exists and is authenticated."""
        if self._old_session is None or self._old_session.closed:
            jar = aiohttp.CookieJar(unsafe=True)
            self._old_session = aiohttp.ClientSession(cookie_jar=jar)
            self._old_api_authenticated = False

        if not self._old_api_authenticated:
            await self._old_api_login()

    async def _old_api_login(self) -> None:
        """Authenticate with the old portal API to get session cookies for writes."""
        if self._old_session is None or self._old_session.closed:
            jar = aiohttp.CookieJar(unsafe=True)
            self._old_session = aiohttp.ClientSession(cookie_jar=jar)

        data = {
            "UserName": self._username,
            "Password": self._password,
        }
        url = f"{API_URL}UserLogon"

        _LOGGER.debug("Logging into old portal API for user %s", self._username)

        try:
            async with asyncio.timeout(20):
                resp = await self._old_session.post(
                    url,
                    json=data,
                    headers=_OLD_API_HEADERS,
                )
                resp.raise_for_status()
                await resp.json()  # consume body
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
    def _parse_uidescription(data: dict) -> dict:
        """Parse the v1.1 uidescription response into components with parameters."""
        result = {"components": []}

        nav_items = data.get("root", {}).get("navigationItems", [])

        for nav_item in nav_items:
            parameters = {}
            _extract_parameters(nav_item, parameters)

            if parameters:
                result["components"].append(
                    {
                        "component_id": nav_item.get("componentId"),
                        "name": nav_item.get("name", "Unknown"),
                        "parameters": parameters,
                    }
                )

        return result

    @staticmethod
    def _parse_csrf_token(html: str) -> str | None:
        """Extract __RequestVerificationToken from login form HTML."""
        match = re.search(
            r'name="__RequestVerificationToken"[\s\S]*?value="([^"]+)"', html
        )
        if match:
            return match.group(1)

        match = re.search(
            r'value="([^"]+)"[\s\S]*?name="__RequestVerificationToken"', html
        )
        if match:
            return match.group(1)

        return None

    @staticmethod
    def _parse_return_url(html: str) -> str | None:
        """Extract ReturnUrl hidden field from login form HTML."""
        match = re.search(
            r'name="ReturnUrl"[\s\S]*?value="([^"]*)"', html
        )
        if match:
            return match.group(1)

        match = re.search(
            r'value="([^"]*)"\s+.*?name="ReturnUrl"', html
        )
        if match:
            return match.group(1)

        return None

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

            # Validate state if provided (OAuth CSRF protection)
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
