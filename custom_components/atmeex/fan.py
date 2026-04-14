"""Fan platform for Atmeex Airnanny."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import (
    FanEntity,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.percentage as pct_util

from .const import DOMAIN, PARAM_FAN_SPEED, PARAM_PWR_ON
from .coordinator import AtmeexCoordinator

_LOGGER = logging.getLogger(__name__)

# Atmeex fan speed mapping (1-based from API)
FAN_SPEEDS = [1, 2, 3]
SPEED_COUNT = len(FAN_SPEEDS)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Atmeex fan platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = []
    for device_id, device_data in coordinator.data.items():
        entities.append(AtmeexFan(coordinator, device_id))

    async_add_entities(entities)


class AtmeexFan(CoordinatorEntity[AtmeexCoordinator], FanEntity):
    """Fan entity for Atmeex breather."""

    _attr_has_entity_name = True
    _attr_speed_count = SPEED_COUNT
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_preset_modes = ["auto", "night"]

    def __init__(
        self,
        coordinator: AtmeexCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        device_data = coordinator.data.get(device_id, {})
        name = device_data.get("name", f"Atmeex {device_id}")

        self._attr_name = "Fan"
        self._attr_unique_id = f"atmeex_{device_id}_fan"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": name,
            "manufacturer": "Atmeex",
            "model": "Airnanny",
            "sw_version": device_data.get("firmware_version", ""),
        }

    @property
    def device_data(self) -> dict[str, Any]:
        """Return current device data."""
        return self.coordinator.data.get(self._device_id, {})

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        return self.device_data.get("pwr_on", False)

    @property
    def percentage(self) -> int | None:
        """Return current fan speed percentage."""
        speed = self.device_data.get("fan_speed", 0)
        if speed == 0:
            return 0
        return pct_util.speed_to_percentage(speed, SPEED_COUNT)

    @property
    def preset_mode(self) -> str | None:
        """Return current preset mode."""
        data = self.device_data
        if data.get("u_night", False):
            return "night"
        if data.get("u_auto", False):
            return "auto"
        return None

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return

        speed = pct_util.percentage_to_speed(percentage, SPEED_COUNT)
        params: dict[str, Any] = {
            PARAM_FAN_SPEED: speed,
            PARAM_PWR_ON: True,
        }
        device_id = self.device_data.get("id")
        if device_id is not None:
            await self.coordinator.api.async_set_device_params(device_id, params)
            await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        params: dict[str, Any] = {
            "u_auto": preset_mode == "auto",
            "u_night": preset_mode == "night",
        }
        device_id = self.device_data.get("id")
        if device_id is not None:
            await self.coordinator.api.async_set_device_params(device_id, params)
            await self.coordinator.async_request_refresh()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        params: dict[str, Any] = {PARAM_PWR_ON: True}
        if percentage is not None:
            params[PARAM_FAN_SPEED] = pct_util.percentage_to_speed(
                percentage, SPEED_COUNT
            )
        device_id = self.device_data.get("id")
        if device_id is not None:
            await self.coordinator.api.async_set_device_params(device_id, params)
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        params: dict[str, Any] = {PARAM_PWR_ON: False}
        device_id = self.device_data.get("id")
        if device_id is not None:
            await self.coordinator.api.async_set_device_params(device_id, params)
            await self.coordinator.async_request_refresh()