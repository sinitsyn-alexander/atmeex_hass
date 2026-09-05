"""Select platform for Atmeex Airnanny."""
from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_OFF_DAMPER_POSITIONS,
    DOMAIN,
    OFF_DAMPER_CLOSED,
    OFF_DAMPER_OPEN,
    PARAM_DAMP_POS,
    PARAM_HUM_STG,
    PARAM_PWR_ON,
)
from .coordinator import AtmeexCoordinator

DAMPER_SUPPLY = "supply"
DAMPER_RECIRCULATION = "recirculation"
DAMPER_MIXED = "mixed"
DAMPER_OPTIONS = [
    DAMPER_SUPPLY,
    DAMPER_RECIRCULATION,
    DAMPER_MIXED,
]

OFF_DAMPER_OPTIONS = [OFF_DAMPER_OPEN, OFF_DAMPER_CLOSED]

HUMIDIFIER_OFF = "off"
HUMIDIFIER_LEVEL_1 = "level_1"
HUMIDIFIER_LEVEL_2 = "level_2"
HUMIDIFIER_OPTIONS = [HUMIDIFIER_OFF, HUMIDIFIER_LEVEL_1, HUMIDIFIER_LEVEL_2]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Atmeex select entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[SelectEntity] = []
    for device_id in coordinator.data:
        entities.append(AtmeexDamperSelect(coordinator, device_id))
        entities.append(AtmeexHumidifierSelect(coordinator, device_id))
        entities.append(AtmeexOffDamperSelect(coordinator, device_id))
    async_add_entities(entities)


class AtmeexSelectBase(CoordinatorEntity[AtmeexCoordinator], SelectEntity):
    """Base class for Atmeex select entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AtmeexCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        device_data = coordinator.data.get(device_id, {})
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": device_data.get("name", f"Atmeex {device_id}"),
            "manufacturer": "Atmeex",
            "model": "Airnanny",
        }

    @property
    def device_data(self) -> dict[str, Any]:
        """Return current device data."""
        return self.coordinator.data.get(self._device_id, {})

    async def _async_set_params(self, params: dict[str, Any]) -> None:
        device_id = self.device_data.get("id")
        if device_id is not None:
            await self.coordinator.api.async_set_device_params(device_id, params)
            await self.coordinator.async_request_refresh()


class AtmeexDamperSelect(AtmeexSelectBase):
    """Damper mode selector."""

    _attr_options = DAMPER_OPTIONS
    _attr_icon = "mdi:air-filter"
    _attr_translation_key = "damper"

    def __init__(self, coordinator: AtmeexCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"atmeex_{device_id}_damper"

    @property
    def current_option(self) -> str | None:
        position = self.device_data.get("u_damp_pos")
        if position is None:
            position = self.device_data.get("damp_pos")
        if position == 0:
            return DAMPER_SUPPLY
        if position == 1:
            return DAMPER_MIXED
        if position == 2:
            return DAMPER_RECIRCULATION
        return None

    async def async_select_option(self, option: str) -> None:
        positions = {
            DAMPER_SUPPLY: 0,
            DAMPER_MIXED: 1,
            DAMPER_RECIRCULATION: 2,
        }
        position = positions.get(option)
        if position is not None:
            await self._async_set_params(
                {PARAM_DAMP_POS: position, PARAM_PWR_ON: True}
            )


class AtmeexHumidifierSelect(AtmeexSelectBase):
    """Humidifier level selector."""

    _attr_options = HUMIDIFIER_OPTIONS
    _attr_icon = "mdi:air-humidifier"
    _attr_translation_key = "humidifier"

    def __init__(self, coordinator: AtmeexCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"atmeex_{device_id}_humidifier"

    @property
    def current_option(self) -> str | None:
        level = self.device_data.get("u_hum_stg")
        if level is None:
            level = self.device_data.get("hum_stg")
        options = {
            0: HUMIDIFIER_OFF,
            1: HUMIDIFIER_LEVEL_1,
            2: HUMIDIFIER_LEVEL_2,
        }
        return options.get(level)

    async def async_select_option(self, option: str) -> None:
        levels = {
            HUMIDIFIER_OFF: 0,
            HUMIDIFIER_LEVEL_1: 1,
            HUMIDIFIER_LEVEL_2: 2,
        }
        level = levels.get(option)
        if level is not None:
            await self._async_set_params({PARAM_HUM_STG: level})


class AtmeexOffDamperSelect(AtmeexSelectBase):
    """Select the damper position used when the breather is turned off."""

    _attr_options = OFF_DAMPER_OPTIONS
    _attr_icon = "mdi:valve"
    _attr_translation_key = "off_damper"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AtmeexCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"atmeex_{device_id}_off_damper"

    @property
    def current_option(self) -> str:
        positions = self.coordinator.entry.options.get(
            CONF_OFF_DAMPER_POSITIONS, {}
        )
        option = positions.get(self._device_id, OFF_DAMPER_OPEN)
        return option if option in OFF_DAMPER_OPTIONS else OFF_DAMPER_OPEN

    async def async_select_option(self, option: str) -> None:
        if option not in OFF_DAMPER_OPTIONS:
            return

        entry = self.coordinator.entry
        options = dict(entry.options)
        positions = dict(options.get(CONF_OFF_DAMPER_POSITIONS, {}))
        positions[self._device_id] = option
        options[CONF_OFF_DAMPER_POSITIONS] = positions
        self.coordinator.hass.config_entries.async_update_entry(
            entry, options=options
        )

        if not self.device_data.get("pwr_on", False):
            await self._async_set_params(
                {PARAM_DAMP_POS: 2 if option == OFF_DAMPER_CLOSED else 0}
            )
