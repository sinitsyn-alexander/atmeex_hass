"""Climate platform for Atmeex Airnanny."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    PARAM_AUTO,
    PARAM_FAN_SPEED,
    PARAM_NIGHT,
    PARAM_PWR_ON,
    PARAM_TEMP_ROOM,
)
from .coordinator import AtmeexCoordinator

_LOGGER = logging.getLogger(__name__)

HEATER_DISABLED = -1000
FAN_MODES = [f"speed_{speed}" for speed in range(1, 8)]
PRESET_MANUAL = "manual"
PRESET_AUTONANNY = "auto"
PRESET_NIGHT = "night"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Atmeex climate platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = []
    for device_id, device_data in coordinator.data.items():
        entities.append(AtmeexClimate(coordinator, device_id))

    async_add_entities(entities)


class AtmeexClimate(CoordinatorEntity[AtmeexCoordinator], ClimateEntity):
    """Climate entity for Atmeex breather."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 10.0
    _attr_max_temp = 30.0
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.FAN_ONLY, HVACMode.HEAT]
    _attr_fan_modes = FAN_MODES
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_preset_modes = [PRESET_MANUAL, PRESET_AUTONANNY, PRESET_NIGHT]
    _attr_translation_key = "climate"

    def __init__(
        self,
        coordinator: AtmeexCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        device_data = coordinator.data.get(device_id, {})
        name = device_data.get("name", f"Atmeex {device_id}")

        self._attr_unique_id = f"atmeex_{device_id}_climate"
        target_temperature = device_data.get("u_temp_room")
        self._last_target_temperature = (
            target_temperature / 10.0
            if target_temperature is not None and target_temperature != HEATER_DISABLED
            else 20.0
        )
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
    def current_temperature(self) -> float | None:
        """Return current room temperature."""
        temp = self.device_data.get("temp_room")
        if temp is not None:
            return temp / 10.0
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return target temperature."""
        temp = self.device_data.get("u_temp_room")
        if temp is not None and temp != HEATER_DISABLED:
            self._last_target_temperature = temp / 10.0
            return self._last_target_temperature
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        data = self.device_data
        if not data.get("pwr_on", False):
            return HVACMode.OFF
        if data.get("u_temp_room") == HEATER_DISABLED:
            return HVACMode.FAN_ONLY
        return HVACMode.HEAT

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan speed."""
        speed = self.device_data.get("u_fan_speed")
        if isinstance(speed, int) and 0 <= speed <= 6:
            return FAN_MODES[speed]
        return None

    @property
    def preset_mode(self) -> str | None:
        """Return current preset mode."""
        data = self.device_data
        if data.get("u_night", False):
            return PRESET_NIGHT
        if data.get("u_auto", False):
            return PRESET_AUTONANNY
        return PRESET_MANUAL

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        params: dict[str, Any] = {}

        if hvac_mode == HVACMode.OFF:
            params[PARAM_PWR_ON] = False
        elif hvac_mode == HVACMode.FAN_ONLY:
            params[PARAM_PWR_ON] = True
            params[PARAM_TEMP_ROOM] = HEATER_DISABLED
        elif hvac_mode == HVACMode.HEAT:
            params[PARAM_PWR_ON] = True
            params[PARAM_TEMP_ROOM] = int(self._last_target_temperature * 10)
        else:
            return

        device_id = self.device_data.get("id")
        if device_id is not None:
            await self.coordinator.api.async_set_device_params(device_id, params)
            await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            params: dict[str, Any] = {
                PARAM_TEMP_ROOM: int(temperature * 10),
                PARAM_PWR_ON: True,
            }
            self._last_target_temperature = temperature
            device_id = self.device_data.get("id")
            if device_id is not None:
                await self.coordinator.api.async_set_device_params(device_id, params)
                await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan speed."""
        if fan_mode not in FAN_MODES:
            return

        params: dict[str, Any] = {
            PARAM_FAN_SPEED: FAN_MODES.index(fan_mode),
            PARAM_PWR_ON: True,
        }
        device_id = self.device_data.get("id")
        if device_id is not None:
            await self.coordinator.api.async_set_device_params(device_id, params)
            await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        if preset_mode not in self.preset_modes:
            return

        params: dict[str, Any] = {
            PARAM_AUTO: preset_mode == PRESET_AUTONANNY,
            PARAM_NIGHT: preset_mode == PRESET_NIGHT,
        }
        device_id = self.device_data.get("id")
        if device_id is not None:
            await self.coordinator.api.async_set_device_params(device_id, params)
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn on the breather in ventilation mode."""
        await self.async_set_hvac_mode(HVACMode.FAN_ONLY)

    async def async_turn_off(self) -> None:
        """Turn off the breather."""
        await self.async_set_hvac_mode(HVACMode.OFF)
