"""The Atmeex Airnanny integration."""
from __future__ import annotations

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import AtmeexApi, AtmeexApiError, AtmeexAuthError
from .const import CONF_ADDRESS_ID, CONF_AUTH_METHOD, CONF_PHONE, DOMAIN
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
        # No tokens — need re-authentication
        _LOGGER.warning("No tokens found, triggering reauth flow")
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

    # Get address_id from entry data
    address_id = entry.data.get(CONF_ADDRESS_ID)

    # Test connection — verify auth works
    try:
        addresses = await api.async_get_addresses()
        _LOGGER.info("Found %d addresses during setup", len(addresses))
    except AtmeexAuthError:
        # Token expired and refresh failed — trigger reauth
        _LOGGER.warning("Token expired and refresh failed, triggering reauth")
        await api.async_close()
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
    except (AtmeexApiError, Exception) as err:
        # Non-auth API error (e.g. 500, network issue) — log but continue setup.
        # The coordinator will retry fetching devices later.
        _LOGGER.warning(
            "Could not fetch devices during setup (will retry via coordinator): %s", err
        )

    coordinator = AtmeexCoordinator(hass, api, address_id=address_id)

    # Initial data fetch — may fail if API returns errors, but still set up entry
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.warning(
            "Initial data fetch failed (will retry): %s", err
        )

    # Store tokens after successful refresh (they may have been updated)
    _async_update_entry_tokens(hass, entry, api)

    # Register listener to persist tokens after every coordinator update
    # (in case they were refreshed due to 401 during periodic polling)
    entry.async_on_unload(
        coordinator.async_add_listener(
            lambda: _async_update_entry_tokens(hass, entry, api)
        )
    )

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