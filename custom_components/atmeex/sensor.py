"""Sensor platform for Atmeex Airnanny."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfTemperature,
)
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
    """Set up Atmeex sensor platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = []
    for device_id, device_data in coordinator.data.items():
        entities.append(AtmeexCO2Sensor(coordinator, device_id))
        entities.append(AtmeexTemperatureSensor(coordinator, device_id))
        entities.append(AtmeexHumiditySensor(coordinator, device_id))
        entities.append(AtmeexSupplyTempSensor(coordinator, device_id))

    async_add_entities(entities)


class AtmeexCO2Sensor(CoordinatorEntity[AtmeexCoordinator], SensorEntity):
    """CO2 sensor for Atmeex breather."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.CO2
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
    _attr_icon = "mdi:molecule-co2"

    def __init__(self, coordinator: AtmeexCoordinator, device_id: str) -> None:
        """Initialize the CO2 sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        device_data = coordinator.data.get(device_id, {})
        name = device_data.get("name", f"Atmeex {device_id}")

        self._attr_name = "CO2"
        self._attr_unique_id = f"atmeex_{device_id}_co2"
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
    def native_value(self) -> int | None:
        """Return CO2 level in ppm."""
        return self.device_data.get("co2_ppm")


class AtmeexTemperatureSensor(CoordinatorEntity[AtmeexCoordinator], SensorEntity):
    """Room temperature sensor for Atmeex breather."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: AtmeexCoordinator, device_id: str) -> None:
        """Initialize the temperature sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        device_data = coordinator.data.get(device_id, {})
        name = device_data.get("name", f"Atmeex {device_id}")

        self._attr_name = "Room Temperature"
        self._attr_unique_id = f"atmeex_{device_id}_temperature"
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
    def native_value(self) -> float | None:
        """Return room temperature in °C."""
        temp = self.device_data.get("temp_room")
        if temp is not None:
            return temp / 10.0
        return None


class AtmeexHumiditySensor(CoordinatorEntity[AtmeexCoordinator], SensorEntity):
    """Humidity sensor for Atmeex breather."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: AtmeexCoordinator, device_id: str) -> None:
        """Initialize the humidity sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        device_data = coordinator.data.get(device_id, {})
        name = device_data.get("name", f"Atmeex {device_id}")

        self._attr_name = "Humidity"
        self._attr_unique_id = f"atmeex_{device_id}_humidity"
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
    def native_value(self) -> int | None:
        """Return humidity percentage."""
        return self.device_data.get("hum_room")


class AtmeexSupplyTempSensor(CoordinatorEntity[AtmeexCoordinator], SensorEntity):
    """Supply air temperature sensor for Atmeex breather."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:thermometer-lines"

    def __init__(self, coordinator: AtmeexCoordinator, device_id: str) -> None:
        """Initialize the supply temperature sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        device_data = coordinator.data.get(device_id, {})
        name = device_data.get("name", f"Atmeex {device_id}")

        self._attr_name = "Supply Air Temperature"
        self._attr_unique_id = f"atmeex_{device_id}_supply_temp"
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
    def native_value(self) -> float | None:
        """Return supply air temperature in °C."""
        temp = self.device_data.get("temp_in")
        if temp is not None:
            return temp / 10.0
        return None