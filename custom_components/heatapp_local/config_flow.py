import logging
from json import JSONDecodeError
from urllib.parse import urlparse

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
        vol.Optional(CONF_INTERVAL, default=30): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
    }
)

def _normalize_base_url(host: str) -> str:
    host = (host or "").strip()
    if not host:
        raise ValueError("Empty host")
    if host.startswith(("http://", "https://")):
        return host.rstrip("/")
    return f"http://{host}".rstrip("/")

def _unique_from_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    netloc = parsed.netloc.lower()
    if ":" not in netloc:
        netloc = f"{netloc}:443" if parsed.scheme == "https" else f"{netloc}:80"
    return f"{parsed.scheme}://{netloc}"

async def validate_input(hass: core.HomeAssistant, data):
    base_url = _normalize_base_url(data[CONF_HOST])
    login = Login(base_url)
    try:
        await hass.async_add_executor_job(
            login.authorize, data[CONF_USER], data[CONF_PASSWORD]
        )
    except requests.exceptions.HTTPError as err:
        resp = getattr(err, "response", None)
        if resp is not None and resp.status_code in (401, 403):
            raise InvalidAuth from err
        raise CannotConnect from err
    except (requests.exceptions.RequestException, JSONDecodeError) as err:
        raise CannotConnect from err

    return {
        "title": base_url,
        "base_url": base_url,
    }

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_UNKNOWN

    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

        errors = {}
        try:
            info = await validate_input(self.hass, user_input)
            await self.async_set_unique_id(_unique_from_url(info["base_url"]))
            self._abort_if_unique_id_configured()
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=info["title"],
                data={
                    CONF_HOST: info["base_url"],
                    CONF_USER: user_input[CONF_USER],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                },
                options={CONF_INTERVAL: user_input.get(CONF_INTERVAL, 30)},
            )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors)

class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate invalid auth."""
