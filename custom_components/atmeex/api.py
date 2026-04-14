"""Atmeex Airnanny API client."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

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
    ) -> Any:
        """Make an HTTP request to the API."""
        session = await self._get_session()
        url = f"{API_BASE_URL}{path}"
        headers: dict[str, str] = {"Content-Type": "application/json"}

        if authenticated and self._access_token:
            headers["Authorization"] = self._access_token

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

            if response.status == 401:
                raise AtmeexAuthError("Authentication failed")

            if response.status == 422:
                resp_data = await response.json()
                _LOGGER.error("Validation error: %s", resp_data)
                raise AtmeexApiError(f"Validation error: {resp_data}")

            response.raise_for_status()

            if response.status == 204:
                return None

            return await response.json()

        except aiohttp.ClientError as err:
            _LOGGER.error("API request failed: %s", err)
            raise AtmeexApiError(f"Request failed: {err}") from err

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
        Returns empty body on success (200 with text/html) — cannot use _request
        because it expects JSON.
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
        """Refresh the access token using refresh token."""
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
            self._refresh_token = result.get("refresh_token")
            _LOGGER.info("Successfully refreshed tokens")
            return result
        except AtmeexAuthError:
            _LOGGER.error("Token refresh failed, need re-authentication")
            raise

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Get list of devices with their current condition."""
        try:
            result = await self._request(
                "GET", "/devices", params={"with_condition": 1}
            )
        except AtmeexAuthError:
            _LOGGER.info("Token expired, trying to refresh...")
            await self.async_refresh_tokens()
            result = await self._request(
                "GET", "/devices", params={"with_condition": 1}
            )
        return result

    async def async_set_device_params(
        self, device_id: int, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Set device parameters (control device)."""
        try:
            result = await self._request(
                "PUT", f"/devices/{device_id}/params", data=params
            )
        except AtmeexAuthError:
            _LOGGER.info("Token expired, trying to refresh...")
            await self.async_refresh_tokens()
            result = await self._request(
                "PUT", f"/devices/{device_id}/params", data=params
            )
        return result

    async def async_get_device(
        self, device_id: int
    ) -> dict[str, Any]:
        """Get single device info."""
        try:
            result = await self._request("GET", f"/devices/{device_id}")
        except AtmeexAuthError:
            _LOGGER.info("Token expired, trying to refresh...")
            await self.async_refresh_tokens()
            result = await self._request("GET", f"/devices/{device_id}")
        return result

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