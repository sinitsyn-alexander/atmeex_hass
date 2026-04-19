"""Atmeex Airnanny API client."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

import aiohttp

from homeassistant.core import HomeAssistant

from .const import API_BASE_URL

_LOGGER = logging.getLogger(__name__)


class AtmeexApiError(Exception):
    """Base exception for Atmeex API errors."""


class AtmeexAuthError(AtmeexApiError):
    """Authentication error."""


class AtmeexApi:
    """Atmeex Airnanny API client."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the API client."""
        self._hass = hass
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._session: aiohttp.ClientSession | None = None
        self.on_tokens_updated: Callable[[], None] | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

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
        session = await self._get_session()
        url = f"{API_BASE_URL}{path}"
        headers: dict[str, str] = {"Content-Type": "application/json"}

        if authenticated and self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"

        _LOGGER.debug("API %s %s params=%s", method, url, params)

        try:
            async with asyncio.timeout(30):
                response = await session.request(
                    method,
                    url,
                    json=data,
                    params=params,
                    headers=headers,
                )

            _LOGGER.debug("Response status: %s for %s %s", response.status, method, url)

            if response.status == 401:
                if authenticated and _retry_on_auth and self._refresh_token:
                    _LOGGER.info("Got 401, refreshing tokens and retrying...")
                    await self.async_refresh_tokens()
                    if self.on_tokens_updated:
                        self.on_tokens_updated()
                    return await self._request(
                        method, path,
                        data=data, params=params,
                        authenticated=authenticated,
                        _retry_on_auth=False,  # only retry once
                    )
                raise AtmeexAuthError("Authentication failed")

            if response.status == 422:
                resp_data = await response.json()
                _LOGGER.error("Validation error: %s", resp_data)
                raise AtmeexApiError(f"Validation error: {resp_data}")

            response.raise_for_status()

            if response.status == 204:
                return None

            content_type = response.headers.get("Content-Type", "")
            if "json" not in content_type:
                _LOGGER.warning(
                    "Unexpected Content-Type '%s' for %s %s",
                    content_type, method, url,
                )
                return None

            return await response.json()

        except aiohttp.ClientError as err:
            _LOGGER.error("API request failed: %s", err)
            raise AtmeexApiError(f"Request failed: {err}") from err

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
        session = await self._get_session()
        url = f"{API_BASE_URL}/auth/signup"
        data = {
            "grant_type": "phone_code",
            "phone": phone,
        }
        headers = {"Content-Type": "application/json"}

        _LOGGER.debug("Sending SMS code to %s via POST %s", phone, url)

        try:
            async with asyncio.timeout(30):
                response = await session.post(url, json=data, headers=headers)

            if response.status == 422:
                resp_data = await response.json()
                _LOGGER.error("SMS send validation error: %s", resp_data)
                raise AtmeexApiError(f"Validation error: {resp_data}")

            response.raise_for_status()
            _LOGGER.info("SMS code sent to %s", phone)

        except aiohttp.ClientError as err:
            _LOGGER.error("SMS send request failed: %s", err)
            raise AtmeexApiError(f"SMS send failed: {err}") from err

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
        """Refresh the access token using refresh token.

        Sends both refresh_token and identity_token (old access_token).
        """
        if not self._refresh_token:
            raise AtmeexAuthError("No refresh token available")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "identity_token": self._access_token,
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
        self,
        address_id: int | None = None,
        room_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get list of devices with their current condition.

        If address_id and room_id are provided, filters by them.
        Otherwise returns all devices (may fail on server side).
        """
        params: dict[str, Any] = {"with_condition": 1}
        if address_id is not None:
            params["address_id"] = address_id
        if room_id is not None:
            params["room_id"] = room_id

        try:
            result = await self._request("GET", "/devices", params=params)
            return result if isinstance(result, list) else []
        except AtmeexApiError:
            _LOGGER.warning("Failed to get devices with params %s", params)
            # Fallback without condition
            params.pop("with_condition", None)
            result = await self._request("GET", "/devices", params=params)
            return result if isinstance(result, list) else []

    async def async_set_device_params(
        self, device_id: int, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Set device parameters (control device)."""
        return await self._request(
            "PUT", f"/devices/{device_id}/params", data=params
        )

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
        """Close the API session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None