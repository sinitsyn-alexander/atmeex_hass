"""Binary sensor platform for Atmeex Airnanny."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AtmeexCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Atmeex binary sensor platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = []
    for device_id, device_data in coordinator.data.items():
        entities.append(AtmeexOnlineSensor(coordinator, device_id))
        entities.append(AtmeexNoWaterSensor(coordinator, device_id))

    async_add_entities(entities)


class AtmeexOnlineSensor(CoordinatorEntity[AtmeexCoordinator], BinarySensorEntity):
    """Online status sensor for Atmeex breather."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: AtmeexCoordinator, device_id: str) -> None:
        """Initialize the online sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        device_data = coordinator.data.get(device_id, {})
        name = device_data.get("name", f"Atmeex {device_id}")

        self._attr_name = "Online"
        self._attr_unique_id = f"atmeex_{device_id}_online"
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
        """Return true if device is online (has recent condition data)."""
        return self.device_data.get("last_update") is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.device_data
        attrs: dict[str, Any] = {}
        if data.get("firmware_version"):
            attrs["firmware_version"] = data["firmware_version"]
        if data.get("network_name"):
            attrs["network_name"] = data["network_name"]
        if data.get("last_update"):
            attrs["last_update"] = data["last_update"]
        return attrs


class AtmeexNoWaterSensor(CoordinatorEntity[AtmeexCoordinator], BinarySensorEntity):
    """No water alert sensor for Atmeex breather."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:water-off"

    def __init__(self, coordinator: AtmeexCoordinator, device_id: str) -> None:
        """Initialize the no water sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        device_data = coordinator.data.get(device_id, {})
        name = device_data.get("name", f"Atmeex {device_id}")

        self._attr_name = "No Water Alert"
        self._attr_unique_id = f"atmeex_{device_id}_no_water"
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
        """Return true if no water alert is active."""
        return self.device_data.get("no_water", False)