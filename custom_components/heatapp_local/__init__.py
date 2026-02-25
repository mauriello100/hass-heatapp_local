"""The heatapp_local integration."""
from _future import annotations

from homeassistant.config_entries import ConfigEntry from homeassistant.const import Platform from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_HOST, CONF_USER, CONF_PASSWORD, CONF_INTERVAL

PLATFORMS: list[Platform] = [Platform.CLIMATE]

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool: """Set up heatapp from a config entry.""" from .coordinator import heatAppDeviceUpdateCoordinator as Coordinator

hass.data.setdefault(DOMAIN, {})

coordinator = Coordinator(
    hass,
    config_entry.data[CONF_HOST],
    config_entry.data[CONF_USER],
    config_entry.data[CONF_PASSWORD],
    config_entry.options.get(CONF_INTERVAL, 30),
)

hass.data[DOMAIN][config_entry.entry_id] = coordinator

await coordinator.async_config_entry_first_refresh()
config_entry.async_on_unload(config_entry.add_update_listener(update_listener))
await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

return True
async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool: """Unload a config entry.""" if unload_ok := await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS): hass.data[DOMAIN].pop(config_entry.entry_id) return unload_ok

async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None: """Handle options updates by reloading the entry.""" await hass.config_entries.async_reload(config_entry.entry_id)

################################
# """The heatapp_local integration."""
# import asyncio
#
# import voluptuous as vol
#
# from homeassistant.config_entries import ConfigEntry
# from homeassistant.core import HomeAssistant
#
# from .const import DOMAIN
#
# CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)
#
# # TODO - DONE List the platforms that you want to support.
# # For your initial PR, limit it to 1 platform.
# PLATFORMS = ["climate"]
#
#
# async def async_setup(hass: HomeAssistant, config: dict):
#     """Set up the heatapp_local component."""
#     return True
#
#
# async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
#     """Set up heatapp_local from a config entry."""
#     # TODO Store an API object for your platforms to access
#     # hass.data[DOMAIN][entry.entry_id] = MyApi(...)
#     #hass.data[DOMAIN][entry.entry_id] = 
#
#     for component in PLATFORMS:
#         hass.async_create_task(
#             hass.config_entries.async_forward_entry_setup(entry, component)
#         )
#
#     return True
#
#
# async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
#     """Unload a config entry."""
#     unload_ok = all(
#         await asyncio.gather(
#             *[
#                 hass.config_entries.async_forward_entry_unload(entry, component)
#                 for component in PLATFORMS
#             ]
#         )
#     )
#     if unload_ok:
#         hass.data[DOMAIN].pop(entry.entry_id)
#
#     return unload_ok
