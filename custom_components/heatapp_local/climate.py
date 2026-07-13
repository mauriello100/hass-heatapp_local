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
    HVACAction,
    HVACMode,
    PRESET_BOOST,
)
from homeassistant.const import (
    ATTR_NAME,
    ATTR_TEMPERATURE,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    UnitOfTemperature,
)

import datetime
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
import asyncio
from .const import DOMAIN
import logging

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
_LOGGER = logging.getLogger(__name__)

PRESET_NONE = "None"
PRESET_HOLIDAY = "Holiday"
PRESET_GO = "Leave"
PRESET_PARTY = "Party"
PRESET_STANDBY = "Standby"

class HeatAppClimateEntity(CoordinatorEntity, ClimateEntity):
    """Representation of a HeatApp Thermostat device."""

    def __init__(self, coordinator, heatappRoomData, apiObject, scene):
        super().__init__(coordinator)
        self.idx = heatappRoomData
        self._apiObject = apiObject
        self._sceneManager = scene
        self._activeMode = ""
        self._activePreset = PRESET_NONE
        self._schedulePeriodsForRoom = {"success": False}
        _LOGGER.info("initializing thermostat: %s", self.idx)

    async def async_added_to_hass(self): 
        await super().async_added_to_hass() 
        try: 
            await self.initOneTimeInformation()
        except Exception as exc: 
            try:
                room_name = self.coordinator.data[self.idx]["name"]
            except (IndexError, KeyError, TypeError):
                room_name = f"Unknown Index {self.idx}"
            _LOGGER.warning("Failed to fetch switching times for %s: %s", room_name, exc) 
            self._schedulePeriodsForRoom = {"success": False}

    async def initOneTimeInformation(self):
        self._schedulePeriodsForRoom = await self.hass.async_add_executor_job(
            self._apiObject.getSwitchingTimes, 
            self.coordinator.data[self.idx]["data"]["name"], 
            self.coordinator.data[self.idx]["data"]["id"]
        )

    def getTodaysSchedule(self):
        if getattr(self, "_schedulePeriodsForRoom", None) and self._schedulePeriodsForRoom.get("success"):            
            weekDayIndex = datetime.datetime.now().weekday()
            listStartIndex = weekDayIndex * 3
            return self._schedulePeriodsForRoom["switchingtimes"][listStartIndex:listStartIndex+3]
        return None

    @property
    def unique_id(self):
        try:
            return self.coordinator.data[self.idx]["name"]
        except (IndexError, KeyError, TypeError):
            return f"heatapp_idx_{self.idx}"

    @property
    def name(self):
        try:
            return self.coordinator.data[self.idx]["name"]
        except (IndexError, KeyError, TypeError):
            return f"HeatApp Zone {self.idx}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "HeatApp (danfoss)",
        }

    @property
    def temperature_unit(self):
        return UnitOfTemperature.CELSIUS

    @property
    def target_temperature(self):
        try:
            desired = self.coordinator.data[self.idx]["data"]["desiredTemperature"]
            return float(desired) if desired is not None else None
        except (IndexError, KeyError, TypeError, ValueError):
            return None

    @property
    def target_temperature_step(self):
        return 0.5

    @property
    def current_temperature(self):
        try:
            actual = self.coordinator.data[self.idx]["data"]["actualTemperature"]
            return float(actual) if actual is not None else None
        except (IndexError, KeyError, TypeError, ValueError):
            return None

    @property
    def min_temp(self):
        try:
            return float(self.coordinator.data[self.idx]["data"]["minTemperature"])
        except (IndexError, KeyError, TypeError, ValueError):
            return 5.0

    @property
    def max_temp(self):
        try:
            return float(self.coordinator.data[self.idx]["data"]["maxTemperature"])
        except (IndexError, KeyError, TypeError, ValueError):
            return 30.0

    @property
    def supported_features(self):
        return SUPPORT_FLAGS

    @property
    def hvac_modes(self):
        return [HVACMode.HEAT, HVACMode.OFF, HVACMode.AUTO, HVACMode.COOL]

    @property
    def preset_mode(self):
        return self._activePreset
        
    async def async_set_preset_mode(self, preset_mode):
        try:
            room_id = self.coordinator.data[self.idx]["data"]["id"]
        except (IndexError, KeyError, TypeError):
            _LOGGER.error("Cannot set preset mode; room identity data is missing for index %s", self.idx)
            return

        if self._activePreset != "":
            if preset_mode != self._activePreset:
                await self.hass.async_add_executor_job(
                    self._sceneManager.removeMemberFromScene, room_id, self._activePreset, True
                )
                if preset_mode == PRESET_NONE:
                    self._activePreset = preset_mode
                if preset_mode != PRESET_NONE:
                    await self.hass.async_add_executor_job(
                        self._sceneManager.addMemberToScene, room_id, preset_mode, True
                    )
                    self._activePreset = preset_mode

    @property
    def preset_modes(self):
        return [PRESET_NONE, PRESET_BOOST, PRESET_HOLIDAY, PRESET_GO, PRESET_PARTY, PRESET_STANDBY]

    @property
    def hvac_mode(self):
        return self._activeMode
