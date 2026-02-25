"""Config flow for heatapp_local integration."""
import logging
from json import JSONDecodeError

import requests
import voluptuous as vol

from homeassistant import config_entries, core, exceptions

from .const import DOMAIN, CONF_USER, CONF_PASSWORD, CONF_HOST, CONF_INTERVAL

from heatapp.login import Login

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        CONF_HOST: str,
        CONF_USER: str,
        CONF_PASSWORD: str,
        CONF_INTERVAL: int,
    }
)


def _normalize_base_url(host: str) -> str:
    """Ensure the host has a scheme and no trailing slash."""
    host = host.strip()
    if host.startswith(("http://", "https://")):
        return host.rstrip("/")
    return f"http://{host}".rstrip("/")


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""
    base_url = _normalize_base_url(data[CONF_HOST])

    login = Login(base_url)

    try:
        # heatapp library is sync, run in executor
        await hass.async_add_executor_job(
            login.authorize, data[CONF_USER], data[CONF_PASSWORD]
        )
    except (requests.exceptions.RequestException, JSONDecodeError) as err:
        # Network/HTTP errors or invalid/empty JSON -> cannot connect
        raise CannotConnect from err

    # If the library provides a specific exception for invalid credentials,
    # catch it above and raise InvalidAuth.

    # Return info to store in the config entry.
    return {
        "title": base_url,
        "data": {
            CONF_HOST: base_url,
            CONF_USER: data[CONF_USER],
            CONF_PASSWORD: data[CONF_PASSWORD],
        },
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for heatapp_local."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_UNKNOWN

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Store host/user/password in data; interval in options
            return self.async_create_entry(
                title=info["title"],
                data=info["data"],
                options={CONF_INTERVAL: user_input[CONF_INTERVAL]},
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
