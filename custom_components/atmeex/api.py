"""Atmeex Airnanny API client."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_BASE_URL

_LOGGER = logging.getLogger(__name__)

API_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "okhttp/3.14.9",
}
COMMAND_SETTLE_DELAY_SECONDS = 2


class AtmeexApiError(Exception):
    """Base exception for Atmeex API errors."""


class AtmeexAuthError(AtmeexApiError):
    """Authentication error."""


class AtmeexTemporaryError(AtmeexApiError):
    """Temporary server or network error."""


class AtmeexApi:
    """Atmeex Airnanny API client."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the API client."""
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._session = async_get_clientsession(hass)
        self._refresh_lock = asyncio.Lock()
        self.on_tokens_updated: Callable[[], None] | None = None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        authenticated: bool = True,
        _retry_on_auth: bool = True,
    ) -> Any:
        """Make an HTTP request to the API.

        On 401 with _retry_on_auth=True, automatically refreshes tokens
        and retries the request once.
        """
        url = f"{API_BASE_URL}{path}"
        headers = dict(API_HEADERS)
        request_access_token = self._access_token

        if authenticated and request_access_token:
            headers["Authorization"] = f"Bearer {request_access_token}"

        _LOGGER.debug("API %s %s params=%s", method, url, params)

        try:
            async with asyncio.timeout(30):
                async with self._session.request(
                    method,
                    url,
                    json=data,
                    params=params,
                    headers=headers,
                ) as response:
                    status = response.status
                    response_text = await response.text()
        except TimeoutError as err:
            _LOGGER.warning("API request timed out: %s %s", method, url)
            raise AtmeexTemporaryError(f"Request timed out: {method} {path}") from err
        except aiohttp.ClientError as err:
            _LOGGER.warning("API request failed: %s", err)
            raise AtmeexTemporaryError(f"Request failed: {err}") from err

        _LOGGER.debug("Response status: %s for %s %s", status, method, url)

        if status == 401:
            if authenticated and _retry_on_auth and self._refresh_token:
                async with self._refresh_lock:
                    if self._access_token == request_access_token:
                        _LOGGER.info("Got 401, refreshing tokens and retrying")
                        await self.async_refresh_tokens()
                        if self.on_tokens_updated:
                            self.on_tokens_updated()
                return await self._request(
                    method,
                    path,
                    data=data,
                    params=params,
                    authenticated=authenticated,
                    _retry_on_auth=False,
                )
            raise AtmeexAuthError("Authentication failed")

        if status == 403:
            raise AtmeexAuthError("Authentication forbidden")

        if status == 429 or status >= 500:
            raise AtmeexTemporaryError(
                f"Server error {status} for {method} {path}"
            )

        if status == 422:
            try:
                response_data = json.loads(response_text)
            except json.JSONDecodeError:
                response_data = response_text
            _LOGGER.error("Validation error: %s", response_data)
            raise AtmeexApiError(f"Validation error: {response_data}")

        if status >= 400:
            raise AtmeexApiError(
                f"Request failed with status {status} for {method} {path}"
            )

        if status == 204 or not response_text:
            return None

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as err:
            _LOGGER.warning("Invalid JSON response for %s %s", method, url)
            raise AtmeexTemporaryError(
                f"Invalid response for {method} {path}"
            ) from err

    # ── Auth methods ──────────────────────────────────────────────

    async def async_login_email(self, email: str, password: str) -> dict[str, Any]:
        """Authenticate with email and password."""
        data = {
            "grant_type": "basic",
            "email": email,
            "password": password,
        }
        result = await self._request(
            "POST", "/auth/signin", data=data, authenticated=False
        )
        self._access_token = result["access_token"]
        self._refresh_token = result.get("refresh_token")
        _LOGGER.info("Successfully authenticated via email")
        return result

    async def async_send_sms_code(self, phone: str) -> None:
        """Send SMS verification code to phone number.

        Uses /auth/signup endpoint with grant_type=phone_code to trigger SMS.
        Returns empty body on success (200 with text/html).
        """
        url = f"{API_BASE_URL}/auth/signup"
        data = {
            "grant_type": "phone_code",
            "phone": phone,
        }
        _LOGGER.debug("Sending SMS code to %s via POST %s", phone, url)

        try:
            async with asyncio.timeout(30):
                async with self._session.post(
                    url, json=data, headers=API_HEADERS
                ) as response:
                    response_text = await response.text()
                    if response.status == 422:
                        raise AtmeexApiError(
                            f"Validation error: {response_text}"
                        )
                    response.raise_for_status()
            _LOGGER.info("SMS code sent to %s", phone)

        except (TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.warning("SMS send request failed: %s", err)
            raise AtmeexTemporaryError(f"SMS send failed: {err}") from err

    async def async_login_phone(self, phone: str, phone_code: str) -> dict[str, Any]:
        """Authenticate with phone number and SMS code."""
        data = {
            "grant_type": "phone_code",
            "phone": phone,
            "phone_code": phone_code,
        }
        result = await self._request(
            "POST", "/auth/signin", data=data, authenticated=False
        )
        self._access_token = result["access_token"]
        self._refresh_token = result.get("refresh_token")
        _LOGGER.info("Successfully authenticated via phone")
        return result

    async def async_refresh_tokens(self) -> dict[str, Any]:
        """Refresh the access token using the refresh token."""
        if not self._refresh_token:
            raise AtmeexAuthError("No refresh token available")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
        }
        try:
            result = await self._request(
                "POST", "/auth/signin", data=data, authenticated=False
            )
            self._access_token = result["access_token"]
            if result.get("refresh_token"):
                self._refresh_token = result["refresh_token"]
            _LOGGER.info("Successfully refreshed tokens")
            return result
        except AtmeexAuthError:
            _LOGGER.error("Token refresh failed, need re-authentication")
            raise

    # ── Hierarchy methods: addresses → rooms → devices ───────────

    async def async_get_addresses(self) -> list[dict[str, Any]]:
        """Get list of addresses for the authenticated user."""
        result = await self._request("GET", "/addresses")
        return result if isinstance(result, list) else []

    async def async_get_rooms(self, address_id: int) -> list[dict[str, Any]]:
        """Get list of rooms for a given address."""
        result = await self._request(
            "GET", "/rooms", params={"address_id": address_id}
        )
        return result if isinstance(result, list) else []

    async def async_get_devices(
        self, address_id: int | None = None
    ) -> list[dict[str, Any]]:
        """Get all devices, including their current condition and settings."""
        params: dict[str, Any] = {"with_condition": 1}
        if address_id is not None:
            params["address_id"] = address_id

        result = await self._request("GET", "/devices", params=params)
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and isinstance(result.get("devices"), list):
            return result["devices"]
        raise AtmeexTemporaryError("Unexpected devices response")

    async def async_set_device_params(
        self, device_id: int, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Set device parameters (control device)."""
        result = await self._request(
            "PUT", f"/devices/{device_id}/params", data=params
        )
        await asyncio.sleep(COMMAND_SETTLE_DELAY_SECONDS)
        return result

    async def async_get_device(
        self, device_id: int
    ) -> dict[str, Any]:
        """Get single device info."""
        return await self._request("GET", f"/devices/{device_id}")

    # ── Token management ──────────────────────────────────────────

    @property
    def access_token(self) -> str | None:
        """Return the current access token."""
        return self._access_token

    @property
    def tokens(self) -> dict[str, str | None]:
        """Return both tokens."""
        return {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
        }

    def restore_tokens(self, access_token: str, refresh_token: str) -> None:
        """Restore tokens from config entry."""
        self._access_token = access_token
        self._refresh_token = refresh_token

    async def async_close(self) -> None:
        """Leave the Home Assistant-managed API session open."""
