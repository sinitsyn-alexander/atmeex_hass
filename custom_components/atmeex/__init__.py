"""The Atmeex Airnanny integration."""
from __future__ import annotations

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import AtmeexApi, AtmeexAuthError
from .const import CONF_AUTH_METHOD, CONF_PHONE, CONF_PHONE_CODE, DOMAIN
from .coordinator import AtmeexCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.FAN,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Atmeex Airnanny from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    api = AtmeexApi(hass)

    # Restore tokens or re-authenticate
    access_token = entry.data.get("access_token")
    refresh_token = entry.data.get("refresh_token")

    if access_token and refresh_token:
        api.restore_tokens(access_token, refresh_token)
    else:
        # Re-authenticate with stored credentials
        auth_method = entry.data.get(CONF_AUTH_METHOD)
        try:
            if auth_method == "email":
                await api.async_login_email(
                    email=entry.data[CONF_EMAIL],
                    password=entry.data[CONF_PASSWORD],
                )
            elif auth_method == "phone":
                await api.async_login_phone(
                    phone=entry.data[CONF_PHONE],
                    phone_code=entry.data[CONF_PHONE_CODE],
                )
        except AtmeexAuthError:
            _LOGGER.error("Authentication failed, trigger reauth")
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={
                        "source": "reauth",
                        "entry_id": entry.entry_id,
                    },
                    data=entry.data,
                )
            )
            return False

    # Test connection
    try:
        await api.async_get_devices()
    except Exception as err:
        await api.async_close()
        raise ConfigEntryNotReady(f"Cannot connect to Atmeex API: {err}") from err

    coordinator = AtmeexCoordinator(hass, api)

    # Initial data fetch
    await coordinator.async_config_entry_first_refresh()

    # Store tokens after successful refresh (they may have been updated)
    _async_update_entry_tokens(hass, entry, api)

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        await entry_data["api"].async_close()

    return unload_ok


def _async_update_entry_tokens(
    hass: HomeAssistant, entry: ConfigEntry, api: AtmeexApi
) -> None:
    """Update stored tokens in config entry if they changed."""
    tokens = api.tokens
    new_access = tokens.get("access_token")
    new_refresh = tokens.get("refresh_token")

    if (
        new_access != entry.data.get("access_token")
        or new_refresh != entry.data.get("refresh_token")
    ):
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, "access_token": new_access, "refresh_token": new_refresh},
        )
        _LOGGER.debug("Updated stored tokens")