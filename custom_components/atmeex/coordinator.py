"""DataUpdateCoordinator for Atmeex Airnanny."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AtmeexApi, AtmeexApiError, AtmeexAuthError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


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
        self._reauth_triggered = False

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from API endpoint."""
        try:
            devices = await self.api.async_get_devices(address_id=self.address_id)
        except AtmeexAuthError as err:
            if not self._reauth_triggered:
                self._reauth_triggered = True
                _LOGGER.error(
                    "Authentication failed, triggering reauth flow: %s", err
                )
                self.hass.async_create_task(
                    self.hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={
                            "source": "reauth",
                            "entry_id": self.entry.entry_id,
                        },
                        data=dict(self.entry.data),
                    )
                )
            raise UpdateFailed(f"Auth failed: {err}") from err
        except AtmeexApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

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
                "u_temp_room": settings.get("u_temp_room"),
                "u_fan_speed": settings.get("u_fan_speed"),
                "u_night_start": settings.get("u_night_start"),
                "u_night_stop": settings.get("u_night_stop"),
            }

        _LOGGER.debug("Updated data for %d devices", len(data))
        return data