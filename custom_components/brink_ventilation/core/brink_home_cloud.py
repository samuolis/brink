"""Brink Home Cloud API client using v1.1 API with OIDC PKCE authentication."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import secrets
import time
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlunsplit, urlparse

import aiohttp

from ..const import (
    API_V1_URL,
    OIDC_AUTH_URL,
    OIDC_CLIENT_ID,
    OIDC_REDIRECT_URI,
    OIDC_SCOPE,
    OIDC_TOKEN_URL,
    PARAM_NAME_MAP,
)

_LOGGER = logging.getLogger(__name__)

_TRUSTED_HOST = "www.brink-home.com"

# valueState enum used in the v1.1 write payload (matches the SPA)
_VALUE_STATE_OK = 0


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
    parameters: dict[str, dict[str, Any]],
    _depth: int = 0,
) -> None:
    """Recursively extract parameters from a navigation item tree.

    Parameters are keyed by canonical string key (matched via PARAM_NAME_MAP
    from the German firmware name). Unrecognized parameters are stored under
    ``"unknown_{numeric_id}"`` so they still appear in diagnostics.
    """
    if _depth > 20:
        _LOGGER.warning("Maximum navigation depth reached, stopping recursion")
        return

    for group in nav_item.get("parameterGroups", []):
        for param in group.get("parameters", []):
            api_name = param.get("name", "")
            param_key = PARAM_NAME_MAP.get(api_name)
            if param_key is None:
                numeric_id = param.get("id")
                if numeric_id is None:
                    continue
                param_key = f"unknown_{numeric_id}"
                _LOGGER.debug(
                    "Unrecognized parameter name %r (id=%s), "
                    "storing as %s",
                    api_name,
                    numeric_id,
                    param_key,
                )

            parameters[param_key] = {
                "name": api_name,
                "value": param.get("value"),
                "value_id": param.get("valueId"),
                "value_state": param.get("valueState"),
                "read_write": param.get("readWrite"),
                "control_type": param.get("controlType"),
                "list_items": param.get("listItems"),
                "min_value": param.get("minValue"),
                "max_value": param.get("maxValue"),
                "unit_of_measure": param.get("unit") or param.get("unitOfMeasure"),
                "component_id": param.get("componentId"),
                "numeric_id": param.get("id"),
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
    """Interacts with Brink Home via the v1.1 API for both reads and writes."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
    ) -> None:
        """Initialize the Brink Home Cloud client.

        Args:
            session: HA shared session for all v1.1 API calls.
            username: Brink Home portal username.
            password: Brink Home portal password.
        """
        self._session = session
        self._username = username
        self._password = password

        # OIDC Bearer token state
        self._access_token: str | None = None
        self._token_expiry: float = 0.0

        # Refresh token for silent token renewal
        self._refresh_token: str | None = None

        # Auth failure backoff state
        self._auth_cooldown_until: float = 0.0
        self._auth_fail_count: int = 0
        self._auth_lock = asyncio.Lock()

    # -------------------------------------------------------------------------
    # Public API methods
    # -------------------------------------------------------------------------

    async def login(self) -> None:
        """Perform OIDC login to obtain a Bearer token."""
        await self._oidc_login()

    async def close(self) -> None:
        """Clear sensitive state. Call on integration unload."""
        self._access_token = None
        self._token_expiry = 0.0
        self._refresh_token = None
        self._auth_cooldown_until = 0.0
        self._auth_fail_count = 0
        self._username = ""
        self._password = ""

    async def get_systems(self) -> list[dict[str, Any]]:
        """Get list of systems from the v1.1 API."""
        await self._ensure_token()

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

        systems: list[dict[str, Any]] = []
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
                    "name": item.get("systemName", "Brink"),
                    "serial_number": item.get("serialNumber", ""),
                    "gateway_state": item.get("gatewayState"),
                }
            )

        if not systems:
            _LOGGER.warning("No systems found in Brink Home API response")

        return systems

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
        params: list[tuple[int, str]],
    ) -> None:
        """Write parameter values via the v1.1 API.

        Uses PUT /systems/{systemId}/parameter-values with Bearer auth.
        Retries once on 401 after re-authenticating.
        """
        if not isinstance(system_id, int):
            raise ValueError(
                f"system_id must be an integer, got {type(system_id).__name__}"
            )

        await self._ensure_token()

        write_values: list[dict[str, Any]] = []
        for vid, val in params:
            if not isinstance(vid, int):
                raise ValueError(
                    f"value_id must be an integer, got {type(vid).__name__}"
                )
            write_values.append({
                "valueId": vid,
                "value": val,
                "state": _VALUE_STATE_OK,
            })

        payload: dict[str, Any] = {"writeValues": write_values}
        url = f"{API_V1_URL}systems/{system_id}/parameter-values"
        _LOGGER.debug("Writing parameters to system %s: %s", system_id, params)

        for attempt in range(2):
            async with asyncio.timeout(20):
                resp = await self._session.put(
                    url,
                    json=payload,
                    headers=self._bearer_headers(),
                )

                if resp.status == 401:
                    await resp.release()
                    if attempt == 0:
                        _LOGGER.debug("Write got 401, refreshing token and retrying")
                        # Force token refresh by expiring it
                        async with self._auth_lock:
                            self._token_expiry = 0.0
                        await self._ensure_token()
                        continue
                    _LOGGER.warning(
                        "Write to Brink API failed: still getting 401 after "
                        "re-authentication — credentials may have changed"
                    )
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
        """Perform OIDC Authorization Code + PKCE flow to get a Bearer token.

        Orchestrates the multi-step OIDC flow by delegating to focused helpers.
        """
        code_verifier, code_challenge, state, nonce = self._build_pkce_challenge()

        jar = aiohttp.CookieJar(unsafe=False)
        async with aiohttp.ClientSession(cookie_jar=jar) as oidc_session:
            login_url, csrf_token, return_url = await self._fetch_login_page(
                oidc_session, code_challenge, state, nonce
            )

            authorization_code = await self._submit_login_credentials(
                oidc_session, login_url, csrf_token, return_url, state
            )

        _LOGGER.debug("Got authorization code, exchanging for token")
        await self._exchange_code_for_tokens(authorization_code, code_verifier)

    def _build_pkce_challenge(self) -> tuple[str, str, str, str]:
        """Generate PKCE challenge parameters for the OIDC flow.

        Returns:
            Tuple of (code_verifier, code_challenge, state, nonce).
        """
        code_verifier = self._generate_code_verifier()
        code_challenge = self._generate_code_challenge(code_verifier)
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        return code_verifier, code_challenge, state, nonce

    async def _fetch_login_page(
        self,
        session: aiohttp.ClientSession,
        code_challenge: str,
        state: str,
        nonce: str,
    ) -> tuple[str, str, str | None]:
        """Fetch the OIDC authorize endpoint and parse the login page.

        Args:
            session: The OIDC session with its own cookie jar.
            code_challenge: PKCE code challenge.
            state: OAuth state parameter.
            nonce: OAuth nonce parameter.

        Returns:
            Tuple of (login_url, csrf_token, return_url).

        Raises:
            BrinkAuthError: If the authorize request fails or the login
                page cannot be parsed.
        """
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
            auth_resp = await session.get(
                OIDC_AUTH_URL,
                params=auth_params,
                allow_redirects=True,
            )

            if auth_resp.status != 200:
                # Log the response body for diagnostics — it often contains
                # the reason (invalid_scope, rate_limited, etc.)
                try:
                    body = await auth_resp.text()
                    # Truncate to avoid flooding the log
                    body_preview = body[:200] if body else "(empty)"
                except asyncio.CancelledError:
                    raise
                except Exception:
                    body_preview = "(could not read body)"
                # Strip query params — they may contain authorization codes
                # or state nonces that should not appear in logs.
                parsed_url = urlparse(str(auth_resp.url))
                safe_url = urlunsplit(
                    (parsed_url.scheme, parsed_url.netloc, parsed_url.path, "", "")
                )
                _LOGGER.debug(
                    "OIDC authorize error body (truncated): %s", body_preview
                )
                _LOGGER.warning(
                    "OIDC authorize returned HTTP %s. "
                    "Final URL (path only): %s",
                    auth_resp.status,
                    safe_url,
                )
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

        # Parse CSRF token and ReturnUrl from login form
        form_fields = self._extract_form_fields(login_page_html)
        csrf_token = form_fields.get("__requestverificationtoken")
        if not csrf_token:
            _LOGGER.warning(
                "Could not find CSRF token in OIDC login page. "
                "The Brink Home website structure may have changed. "
                "This is NOT a credentials issue — please report it at "
                "https://github.com/samuolis/brink/issues"
            )
            raise BrinkAuthError(
                "Could not find CSRF token in OIDC login page"
            )

        return_url = form_fields.get("returnurl")
        return login_url, csrf_token, return_url

    async def _submit_login_credentials(
        self,
        session: aiohttp.ClientSession,
        login_url: str,
        csrf_token: str,
        return_url: str | None,
        expected_state: str,
    ) -> str:
        """Submit login credentials and extract the authorization code.

        Args:
            session: The OIDC session with its own cookie jar.
            login_url: URL to POST the login form to.
            csrf_token: CSRF token from the login page.
            return_url: Optional ReturnUrl from the login form.
            expected_state: OAuth state parameter for CSRF validation.

        Returns:
            The authorization code string.

        Raises:
            BrinkAuthError: If login fails or the authorization code
                cannot be extracted.
        """
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
            login_resp = await session.post(
                login_url,
                data=form_data,
                allow_redirects=False,
            )

            authorization_code: str | None = None

            if login_resp.status in (301, 302, 303, 307):
                redirect_location = login_resp.headers.get("Location", "")
                await login_resp.release()
                authorization_code = self._extract_code_from_redirect(
                    redirect_location, expected_state=expected_state
                )

                if not authorization_code:
                    _LOGGER.debug(
                        "Following redirect chain to get auth code"
                    )
                    authorization_code = await self._follow_redirects_for_code(
                        session, redirect_location, login_url, expected_state
                    )
            elif login_resp.status == 200:
                body = await login_resp.text()
                if "invalid" in body.lower() or "error" in body.lower():
                    raise BrinkAuthError(
                        "Invalid username or password",
                        is_credentials_error=True,
                    )
                _LOGGER.warning(
                    "OIDC login returned 200 without redirect. "
                    "The Brink Home login flow may have changed. "
                    "If your credentials are correct, please report this at "
                    "https://github.com/samuolis/brink/issues"
                )
                raise BrinkAuthError(
                    "OIDC login returned 200 - credentials may be invalid"
                )
            else:
                _LOGGER.warning(
                    "OIDC login returned unexpected HTTP %s. "
                    "The Brink Home website may have changed. "
                    "Please report this at "
                    "https://github.com/samuolis/brink/issues",
                    login_resp.status,
                )
                raise BrinkAuthError(
                    f"OIDC login failed with status {login_resp.status}"
                )

        if not authorization_code:
            _LOGGER.warning(
                "OIDC login completed but no authorization code was found "
                "in the redirect chain. The Brink Home login flow may have "
                "changed. Please report this at "
                "https://github.com/samuolis/brink/issues"
            )
            raise BrinkAuthError(
                "Could not extract authorization code from OIDC flow"
            )

        return authorization_code

    async def _exchange_code_for_tokens(
        self,
        authorization_code: str,
        code_verifier: str,
    ) -> None:
        """Exchange an authorization code for access and refresh tokens.

        Args:
            authorization_code: The code obtained from the OIDC redirect.
            code_verifier: The PKCE code verifier matching the original challenge.

        Raises:
            BrinkAuthError: If the token exchange fails or the response
                is missing the access token.
        """
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
                _LOGGER.warning(
                    "OIDC token exchange failed with HTTP %s. "
                    "The Brink Home authentication flow may have changed. "
                    "Please report this at "
                    "https://github.com/samuolis/brink/issues",
                    token_resp.status,
                )
                raise BrinkAuthError(
                    f"OIDC token exchange failed with status {token_resp.status}"
                )

            token_json = await token_resp.json()
            await token_resp.release()

        access_token = token_json.get("access_token")
        if not access_token:
            _LOGGER.warning(
                "OIDC token response missing access_token field. "
                "The Brink Home authentication flow may have changed. "
                "Please report this at "
                "https://github.com/samuolis/brink/issues"
            )
            raise BrinkAuthError(
                "OIDC token response did not contain an access token"
            )
        self._access_token = access_token
        expires_in: int = token_json.get("expires_in", 3599)
        self._token_expiry = time.monotonic() + expires_in - 60

        # Store refresh token if the server provided one
        refresh_token = token_json.get("refresh_token")
        if refresh_token:
            self._refresh_token = refresh_token
            # Immediately verify the refresh token works so the user gets
            # feedback now, not in ~1 hour when the access token expires.
            try:
                await self._refresh_access_token()
                _LOGGER.debug(
                    "OIDC login successful, refresh token verified — "
                    "silent token renewal is active"
                )
            except BrinkAuthError:
                # Restore the refresh token — it may still be valid,
                # the verification failure could be transient (timeout etc.)
                self._refresh_token = refresh_token
                _LOGGER.warning(
                    "Refresh token verification failed — will fall back to "
                    "full OIDC re-authentication on token expiry"
                )
        else:
            self._refresh_token = None
            _LOGGER.info(
                "OIDC login successful — full re-authentication will be "
                "required every ~%s seconds (no refresh token issued)",
                expires_in,
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
            except (aiohttp.ClientError, asyncio.TimeoutError) as redir_ex:
                _LOGGER.warning(
                    "OIDC redirect chain interrupted: %s", redir_ex
                )
                break

        return None

    # -------------------------------------------------------------------------
    # Token management
    # -------------------------------------------------------------------------

    async def _ensure_token(self) -> None:
        """Ensure we have a valid Bearer token, using refresh or full OIDC.

        Uses exponential backoff on repeated failures to avoid hammering
        the server. Backoff schedule: 60s, 120s, 240s, 480s, 900s (cap).
        """
        if self._access_token and time.monotonic() < self._token_expiry:
            return

        async with self._auth_lock:
            # Re-check after acquiring lock (another coroutine may have refreshed)
            if self._access_token and time.monotonic() < self._token_expiry:
                return

            # Check cooldown before hitting the server
            now = time.monotonic()
            if now < self._auth_cooldown_until:
                remaining = int(self._auth_cooldown_until - now)
                raise BrinkAuthError(
                    f"Authentication on cooldown, next retry in {remaining}s"
                )

            # Try refresh token first (silent, no full OIDC flow)
            if self._refresh_token:
                try:
                    await self._refresh_access_token()
                    self._auth_fail_count = 0
                    self._auth_cooldown_until = 0.0
                    return
                except BrinkAuthError:
                    _LOGGER.info(
                        "Refresh token expired or revoked, "
                        "falling back to full OIDC login"
                    )
                    # _refresh_access_token already cleared self._refresh_token

            # Full OIDC login as last resort
            _LOGGER.debug("Performing full OIDC login")
            try:
                await self._oidc_login()
                self._auth_fail_count = 0
                self._auth_cooldown_until = 0.0
            except BrinkAuthError:
                self._auth_fail_count = min(self._auth_fail_count + 1, 5)
                backoff = min(60 * (2 ** (self._auth_fail_count - 1)), 900)
                self._auth_cooldown_until = time.monotonic() + backoff
                _LOGGER.warning(
                    "OIDC authentication failed (attempt %s), "
                    "backing off for %s seconds before next retry",
                    self._auth_fail_count,
                    backoff,
                )
                raise

    def _bearer_headers(self) -> dict[str, str]:
        """Return headers with Bearer token for v1.1 API calls."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }

    async def _refresh_access_token(self) -> None:
        """Use the refresh token to silently obtain a new access token.

        Raises BrinkAuthError if the refresh fails (token expired/revoked).
        On failure, clears the stored refresh token so the caller falls
        back to a full OIDC login.
        """
        if not self._refresh_token:
            raise BrinkAuthError("No refresh token available")

        token_data: dict[str, str] = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": OIDC_CLIENT_ID,
        }

        try:
            async with asyncio.timeout(20):
                resp = await self._session.post(
                    OIDC_TOKEN_URL,
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                if resp.status != 200:
                    self._refresh_token = None
                    await resp.release()
                    raise BrinkAuthError(
                        f"Refresh token rejected (HTTP {resp.status})"
                    )

                try:
                    token_json = await resp.json()
                except Exception:
                    self._refresh_token = None
                    await resp.release()
                    raise BrinkAuthError("Refresh response was not valid JSON")

                access_token = token_json.get("access_token")
                if not access_token:
                    self._refresh_token = None
                    await resp.release()
                    raise BrinkAuthError("Refresh response missing access_token")
        except (aiohttp.ClientError, asyncio.TimeoutError) as ex:
            self._refresh_token = None
            raise BrinkAuthError(
                f"Refresh token request failed: {type(ex).__name__}"
            ) from ex

        self._access_token = access_token
        expires_in: int = token_json.get("expires_in", 3599)
        self._token_expiry = time.monotonic() + expires_in - 60

        # Servers often rotate refresh tokens — store the new one if provided
        new_refresh = token_json.get("refresh_token")
        if new_refresh:
            self._refresh_token = new_refresh

        _LOGGER.debug(
            "Access token refreshed silently (expires in %ss)", expires_in
        )

    # -------------------------------------------------------------------------
    # Parsing helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_uidescription(data: dict[str, Any]) -> dict[str, Any]:
        """Parse the v1.1 uidescription response into components with parameters."""
        nav_items = data.get("root", {}).get("navigationItems", [])

        components: list[dict[str, Any]] = []
        for nav_item in nav_items:
            parameters: dict[str, dict[str, Any]] = {}
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
    """Raised when Brink Home authentication fails.

    Attributes:
        is_credentials_error: True only when the failure is definitely
            caused by wrong username/password.  False for server errors,
            CSRF issues, token exchange failures, etc.
    """

    def __init__(
        self, message: str, *, is_credentials_error: bool = False
    ) -> None:
        super().__init__(message)
        self.is_credentials_error = is_credentials_error
