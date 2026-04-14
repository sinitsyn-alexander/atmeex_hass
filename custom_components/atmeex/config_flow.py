"""Config flow for Atmeex Airnanny integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult

from .api import AtmeexApi, AtmeexApiError, AtmeexAuthError
from .const import (
    AUTH_METHOD_EMAIL,
    AUTH_METHOD_PHONE,
    CONF_ADDRESS_ID,
    CONF_ADDRESS_NAME,
    CONF_AUTH_METHOD,
    CONF_PHONE,
    CONF_PHONE_CODE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class AtmeexConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Atmeex Airnanny."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._auth_method: str | None = None
        self._phone: str | None = None
        self._api: AtmeexApi | None = None
        self._addresses: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - choose auth method."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._auth_method = user_input[CONF_AUTH_METHOD]
            if self._auth_method == AUTH_METHOD_EMAIL:
                return await self.async_step_email()
            return await self.async_step_phone()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AUTH_METHOD, default=AUTH_METHOD_EMAIL): vol.In(
                        {
                            AUTH_METHOD_EMAIL: "Email и пароль",
                            AUTH_METHOD_PHONE: "Телефон и SMS-код",
                        }
                    ),
                }
            ),
            errors=errors,
            description_placeholders={},
        )

    async def async_step_email(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle email + password authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                api = AtmeexApi(self.hass)
                await api.async_login_email(
                    email=user_input[CONF_EMAIL],
                    password=user_input[CONF_PASSWORD],
                )
                self._api = api
                # Get addresses for selection
                return await self._get_addresses_or_finish()
            except AtmeexAuthError:
                errors["base"] = "invalid_auth"
            except AtmeexApiError as err:
                _LOGGER.error("API error during email login: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="email",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={},
        )

    async def async_step_phone(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle phone number entry step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._phone = user_input[CONF_PHONE]
            # Send SMS code via /auth/signup
            try:
                api = AtmeexApi(self.hass)
                await api.async_send_sms_code(self._phone)
                await api.async_close()
            except AtmeexApiError:
                errors["base"] = "sms_send_failed"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception sending SMS")
                errors["base"] = "unknown"

            if not errors:
                return await self.async_step_phone_code()

        return self.async_show_form(
            step_id="phone",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PHONE): str,
                }
            ),
            errors=errors,
            description_placeholders={},
        )

    async def async_step_phone_code(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle SMS code entry step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                api = AtmeexApi(self.hass)
                await api.async_login_phone(
                    phone=self._phone or "",
                    phone_code=user_input[CONF_PHONE_CODE],
                )
                self._api = api
                # Get addresses for selection
                return await self._get_addresses_or_finish()
            except AtmeexAuthError:
                errors["base"] = "invalid_auth"
            except AtmeexApiError as err:
                _LOGGER.error("API error during phone login: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="phone_code",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PHONE_CODE): str,
                }
            ),
            errors=errors,
            description_placeholders={"phone": self._phone or ""},
        )

    async def _get_addresses_or_finish(self) -> FlowResult:
        """Get addresses from API. If only one, auto-select. Otherwise, show selection."""
        assert self._api is not None

        try:
            self._addresses = await self._api.async_get_addresses()
        except (AtmeexApiError, Exception) as err:
            _LOGGER.warning("Could not fetch addresses: %s", err)
            self._addresses = []

        await self._api.async_close()

        if len(self._addresses) == 0:
            return self.async_abort(reason="no_addresses")

        if len(self._addresses) == 1:
            # Auto-select single address
            addr = self._addresses[0]
            return self._create_entry(addr)

        # Multiple addresses — show selection step
        return await self.async_step_select_address()

    async def async_step_select_address(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle address selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_id = user_input[CONF_ADDRESS_ID]
            # Find the selected address
            for addr in self._addresses:
                if str(addr["id"]) == str(selected_id):
                    return self._create_entry(addr)
            errors["base"] = "unknown"

        # Build address options dict
        address_options = {
            str(addr["id"]): addr["name"] for addr in self._addresses
        }

        return self.async_show_form(
            step_id="select_address",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS_ID): vol.In(address_options),
                }
            ),
            errors=errors,
            description_placeholders={},
        )

    def _create_entry(self, address: dict[str, Any]) -> FlowResult:
        """Create a config entry with the selected address and tokens."""
        assert self._api is not None

        title = f"Atmeex ({address['name']})"
        auth_method = self._auth_method or AUTH_METHOD_EMAIL

        data: dict[str, Any] = {
            CONF_AUTH_METHOD: auth_method,
            CONF_ADDRESS_ID: address["id"],
            CONF_ADDRESS_NAME: address["name"],
            "access_token": self._api.access_token,
            "refresh_token": self._api.tokens.get("refresh_token"),
        }

        # Store credentials for reauth
        if auth_method == AUTH_METHOD_EMAIL:
            # Email credentials are in the flow but not stored in previous steps
            # We don't have them here — reauth will ask again
            pass
        elif auth_method == AUTH_METHOD_PHONE:
            data[CONF_PHONE] = self._phone

        return self.async_create_entry(title=title, data=data)

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Handle re-authentication."""
        self._auth_method = entry_data.get(CONF_AUTH_METHOD, AUTH_METHOD_EMAIL)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if entry is None:
            return self.async_abort(reason="unknown")

        if self._auth_method == AUTH_METHOD_EMAIL:
            if user_input is not None:
                try:
                    api = AtmeexApi(self.hass)
                    await api.async_login_email(
                        email=user_input[CONF_EMAIL],
                        password=user_input[CONF_PASSWORD],
                    )
                    await api.async_close()

                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={
                            **entry.data,
                            CONF_EMAIL: user_input[CONF_EMAIL],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            "access_token": api.access_token,
                            "refresh_token": api.tokens.get("refresh_token"),
                        },
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
                except AtmeexAuthError:
                    errors["base"] = "invalid_auth"
                except AtmeexApiError:
                    errors["base"] = "cannot_connect"

            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_EMAIL, default=entry.data.get(CONF_EMAIL, "")): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
                errors=errors,
            )

        # Phone reauth — go to phone step
        return await self.async_step_phone()