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
    CONF_ON_DAMPER_POSITIONS,
    DOMAIN,
    OFF_DAMPER_CLOSED,
    OFF_DAMPER_OPEN,
    ON_DAMPER_MIXED,
    ON_DAMPER_RECIRCULATION,
    ON_DAMPER_SUPPLY,
    PARAM_DAMP_POS,
    PARAM_HUM_STG,
)
from .coordinator import AtmeexCoordinator

ON_DAMPER_OPTIONS = [
    ON_DAMPER_SUPPLY,
    ON_DAMPER_MIXED,
    ON_DAMPER_RECIRCULATION,
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
    options = dict(entry.options)
    on_positions = dict(options.get(CONF_ON_DAMPER_POSITIONS, {}))
    options_changed = False

    for device_id, device_data in coordinator.data.items():
        if on_positions.get(device_id) in ON_DAMPER_OPTIONS:
            continue

        position = device_data.get("u_damp_pos")
        if position is None:
            position = device_data.get("damp_pos")
        on_positions[device_id] = (
            {
                1: ON_DAMPER_MIXED,
                2: ON_DAMPER_RECIRCULATION,
            }.get(position, ON_DAMPER_SUPPLY)
            if device_data.get("pwr_on", False)
            else ON_DAMPER_SUPPLY
        )
        options_changed = True

    if options_changed:
        options[CONF_ON_DAMPER_POSITIONS] = on_positions
        hass.config_entries.async_update_entry(entry, options=options)

    entities: list[SelectEntity] = []
    for device_id in coordinator.data:
        entities.append(AtmeexOnDamperSelect(coordinator, device_id))
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

    async def _async_device_is_on(self) -> bool:
        """Return the current power state directly from the API."""
        device_id = self.device_data.get("id")
        if device_id is None:
            return bool(self.device_data.get("pwr_on", False))

        device = await self.coordinator.api.async_get_device(device_id)
        if not isinstance(device, dict):
            return bool(self.device_data.get("pwr_on", False))

        condition = device.get("condition") or {}
        if "pwr_on" in condition:
            return bool(condition["pwr_on"])

        settings = device.get("settings") or {}
        if "u_pwr_on" in settings:
            return bool(settings["u_pwr_on"])
        return bool(self.device_data.get("pwr_on", False))


class AtmeexOnDamperSelect(AtmeexSelectBase):
    """Select the damper position used while the breather is on."""

    _attr_options = ON_DAMPER_OPTIONS
    _attr_icon = "mdi:air-filter"
    _attr_translation_key = "on_damper"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AtmeexCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"atmeex_{device_id}_damper"

    @property
    def current_option(self) -> str:
        positions = self.coordinator.entry.options.get(
            CONF_ON_DAMPER_POSITIONS, {}
        )
        option = positions.get(self._device_id)
        if option in ON_DAMPER_OPTIONS:
            return option

        if not self.device_data.get("pwr_on", False):
            return ON_DAMPER_SUPPLY

        position = self.device_data.get("u_damp_pos")
        if position is None:
            position = self.device_data.get("damp_pos")
        return {
            0: ON_DAMPER_SUPPLY,
            1: ON_DAMPER_MIXED,
            2: ON_DAMPER_RECIRCULATION,
        }.get(position, ON_DAMPER_SUPPLY)

    async def async_select_option(self, option: str) -> None:
        if option not in ON_DAMPER_OPTIONS:
            return

        entry = self.coordinator.entry
        options = dict(entry.options)
        positions = dict(options.get(CONF_ON_DAMPER_POSITIONS, {}))
        positions[self._device_id] = option
        options[CONF_ON_DAMPER_POSITIONS] = positions
        self.coordinator.hass.config_entries.async_update_entry(
            entry, options=options
        )

        if await self._async_device_is_on():
            damp_positions = {
                ON_DAMPER_SUPPLY: 0,
                ON_DAMPER_MIXED: 1,
                ON_DAMPER_RECIRCULATION: 2,
            }
            await self._async_set_params(
                {PARAM_DAMP_POS: damp_positions[option]}
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

        if not await self._async_device_is_on():
            await self._async_set_params(
                {PARAM_DAMP_POS: 2 if option == OFF_DAMPER_CLOSED else 0}
            )
