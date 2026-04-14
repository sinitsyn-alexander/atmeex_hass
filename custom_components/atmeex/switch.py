"""Switch platform for Atmeex Airnanny."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PARAM_COOL_MODE, PARAM_NIGHT
from .coordinator import AtmeexCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Atmeex switch platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = []
    for device_id, device_data in coordinator.data.items():
        entities.append(AtmeexCoolModeSwitch(coordinator, device_id))
        entities.append(AtmeexNightModeSwitch(coordinator, device_id))

    async_add_entities(entities)


class AtmeexCoolModeSwitch(CoordinatorEntity[AtmeexCoordinator], SwitchEntity):
    """Cool mode switch for Atmeex breather."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:snowflake"

    def __init__(self, coordinator: AtmeexCoordinator, device_id: str) -> None:
        """Initialize the cool mode switch."""
        super().__init__(coordinator)
        self._device_id = device_id
        device_data = coordinator.data.get(device_id, {})
        name = device_data.get("name", f"Atmeex {device_id}")

        self._attr_name = "Cool Mode"
        self._attr_unique_id = f"atmeex_{device_id}_cool_mode"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": name,
            "manufacturer": "Atmeex",
            "model": "Airnanny",
        }

    @property
    def device_data(self) -> dict[str, Any]:
        """Return current device data."""
        return self.coordinator.data.get(self._device_id, {})

    @property
    def is_on(self) -> bool:
        """Return true if cool mode is enabled."""
        return self.device_data.get("cool_mode", False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on cool mode."""
        params: dict[str, Any] = {PARAM_COOL_MODE: True}
        device_id = self.device_data.get("id")
        if device_id is not None:
            await self.coordinator.api.async_set_device_params(device_id, params)
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off cool mode."""
        params: dict[str, Any] = {PARAM_COOL_MODE: False}
        device_id = self.device_data.get("id")
        if device_id is not None:
            await self.coordinator.api.async_set_device_params(device_id, params)
            await self.coordinator.async_request_refresh()


class AtmeexNightModeSwitch(CoordinatorEntity[AtmeexCoordinator], SwitchEntity):
    """Night mode switch for Atmeex breather."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:weather-night"

    def __init__(self, coordinator: AtmeexCoordinator, device_id: str) -> None:
        """Initialize the night mode switch."""
        super().__init__(coordinator)
        self._device_id = device_id
        device_data = coordinator.data.get(device_id, {})
        name = device_data.get("name", f"Atmeex {device_id}")

        self._attr_name = "Night Mode"
        self._attr_unique_id = f"atmeex_{device_id}_night_mode"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": name,
            "manufacturer": "Atmeex",
            "model": "Airnanny",
        }

    @property
    def device_data(self) -> dict[str, Any]:
        """Return current device data."""
        return self.coordinator.data.get(self._device_id, {})

    @property
    def is_on(self) -> bool:
        """Return true if night mode is enabled."""
        return self.device_data.get("u_night", False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.device_data
        attrs: dict[str, Any] = {}
        if data.get("u_night_start"):
            attrs["night_start"] = data["u_night_start"]
        if data.get("u_night_stop"):
            attrs["night_stop"] = data["u_night_stop"]
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on night mode."""
        params: dict[str, Any] = {PARAM_NIGHT: True}
        device_id = self.device_data.get("id")
        if device_id is not None:
            await self.coordinator.api.async_set_device_params(device_id, params)
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off night mode."""
        params: dict[str, Any] = {PARAM_NIGHT: False}
        device_id = self.device_data.get("id")
        if device_id is not None:
            await self.coordinator.api.async_set_device_params(device_id, params)
            await self.coordinator.async_request_refresh()