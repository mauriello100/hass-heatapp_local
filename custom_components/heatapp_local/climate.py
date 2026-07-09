from homeassistant.config_entries import ConfigEntry
from .const import CONF_USER, CONF_PASSWORD, CONF_HOST
from heatapp.apiMethods import ApiMethods
from heatapp.login import Login
from heatapp.sceneManager import SceneManager
from homeassistant import config_entries
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import (
    UnitOfTemperature,
    ATTR_TEMPERATURE,
)

import datetime
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
import logging
from .const import DOMAIN

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
_LOGGER = logging.getLogger(__name__)

PRESET_NONE = "None"
PRESET_BOOST = "Boost"
PRESET_HOLIDAY = "Holiday"
PRESET_GO = "Leave"
PRESET_PARTY = "Party"
PRESET_STANDBY = "Standby"

async def async_setup_entry(hass: HomeAssistant, config_entry: config_entries.ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the climate platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    api = coordinator.api
    sceneManager = SceneManager(api)
    
    async_add_entities(
        HeatAppClimateEntity(coordinator, i, api, sceneManager) for i in range(len(coordinator.data))
    )

class HeatAppClimateEntity(CoordinatorEntity, ClimateEntity):
    """Representation of a HeatApp Thermostat device."""

    def __init__(self, coordinator, idx, apiObject, scene):
        super().__init__(coordinator)
        self.idx = idx
        self._apiObject = apiObject
        self._sceneManager = scene
        self._activePreset = PRESET_NONE
        self._schedulePeriodsForRoom = {"success": False}

    async def async_added_to_hass(self): 
        await super().async_added_to_hass() 
        try: 
            await self.initOneTimeInformation()
        except Exception as exc: 
            _LOGGER.warning("Failed to fetch switching times for index %s: %s", self.idx, exc) 

    async def initOneTimeInformation(self):
        self._schedulePeriodsForRoom = await self.hass.async_add_executor_job(
            self._apiObject.getSwitchingTimes, 
            self.coordinator.data[self.idx]["data"]["name"],
