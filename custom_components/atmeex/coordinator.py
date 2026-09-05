"""DataUpdateCoordinator for Atmeex Airnanny."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AtmeexApi, AtmeexApiError, AtmeexAuthError, AtmeexTemporaryError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)
STALE_DATA_MAX_AGE_SECONDS = 15 * 60
ROOM_IDS_REFRESH_SECONDS = 60 * 60


class AtmeexCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator to manage data updates from Atmeex API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: AtmeexApi,
        entry: Any,
        address_id: int | None = None,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self.address_id = address_id
        self.entry = entry
        self._room_ids: set[str] | None = None
        self._room_ids_refreshed_at: float | None = None
        self._last_success_data: dict[str, dict[str, Any]] = {}
        self._last_success_monotonic: float | None = None

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from API endpoint."""
        try:
            now = self.hass.loop.time()
            if self.address_id is not None and (
                self._room_ids_refreshed_at is None
                or now - self._room_ids_refreshed_at >= ROOM_IDS_REFRESH_SECONDS
            ):
                rooms = await self.api.async_get_rooms(self.address_id)
                self._room_ids = {str(room["id"]) for room in rooms if "id" in room}
                self._room_ids_refreshed_at = now
            devices = await self.api.async_get_devices()
        except AtmeexAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AtmeexTemporaryError as err:
            if self._last_success_monotonic is not None:
                elapsed = self.hass.loop.time() - self._last_success_monotonic
                if elapsed < STALE_DATA_MAX_AGE_SECONDS:
                    _LOGGER.warning(
                        "Using stale Atmeex data due to temporary API error: %s", err
                    )
                    return self._last_success_data
            raise UpdateFailed(f"Temporary API error: {err}") from err
        except AtmeexApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        if self._room_ids is not None:
            devices = [
                device
                for device in devices
                if str(device.get("room_id")) in self._room_ids
            ]

        if not devices or not isinstance(devices, list):
            _LOGGER.debug("No devices returned from API")
            return {}

        data: dict[str, dict[str, Any]] = {}
        for device in devices:
            device_id = str(device.get("id", ""))
            condition = device.get("condition") or {}
            settings = device.get("settings") or {}

            data[device_id] = {
                "id": device.get("id"),
                "name": device.get("name", f"Atmeex {device_id}"),
                "mac": device.get("mac", ""),
                "type": device.get("type"),
                "room_id": device.get("room_id"),
                "condition": condition,
                "settings": settings,
                # Flatten commonly used condition fields for easy access
                "pwr_on": condition.get("pwr_on", False),
                "fan_speed": condition.get("fan_speed", 0),
                "co2_ppm": condition.get("co2_ppm"),
                "temp_room": condition.get("temp_room"),
                "temp_in": condition.get("temp_in"),
                "hum_room": condition.get("hum_room"),
                "damp_pos": condition.get("damp_pos", 0),
                "cool_mode": condition.get("cool_mode", False),
                "no_water": condition.get("no_water", False),
                "hum_stg": condition.get("hum_stg", 0),
                "firmware_version": condition.get("firmware_version", ""),
                "network_name": condition.get("network_name", ""),
                "last_update": condition.get("time"),
                # Settings fields
                "u_auto": settings.get("u_auto", False),
                "u_night": settings.get("u_night", False),
                "u_pwr_on": settings.get("u_pwr_on"),
                "u_temp_room": settings.get("u_temp_room"),
                "u_fan_speed": settings.get("u_fan_speed"),
                "u_damp_pos": settings.get("u_damp_pos"),
                "u_hum_stg": settings.get("u_hum_stg"),
                "u_night_start": settings.get("u_night_start"),
                "u_night_stop": settings.get("u_night_stop"),
            }

        _LOGGER.debug("Updated data for %d devices", len(data))
        self._last_success_data = data
        self._last_success_monotonic = self.hass.loop.time()
        return data
