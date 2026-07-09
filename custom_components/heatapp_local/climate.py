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

from .const import (
    DOMAIN
)
import logging

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE

_LOGGER = logging.getLogger(__name__)

PRESET_NONE = "None"
PRESET_BOOST = "Boost"
PRESET_HOLIDAY = "Holiday"
PRESET_GO = "Leave"
PRESET_PARTY = "Party"
PRESET_STANDBY = "Standby"

api = None
credentials = None
sceneManager = None
coordinator = None

async def async_setup_integration(hass, config_entry: config_entries.ConfigEntry, async_add_entities):
    raw_host = str(config_entry.data[CONF_HOST]).strip()
    if raw_host.startswith(("http://", "https://")):
        base_url = raw_host.rstrip("/")
    else:
        base_url = f"http://{raw_host.rstrip('/')}"
        
    loginManager = Login(base_url)
    try:
        credentials = await hass.async_add_executor_job(
            loginManager.authorize, config_entry.data[CONF_USER], config_entry.data[CONF_PASSWORD]
        )
    except Exception as exc:
        _LOGGER.error("Authorization failed against %s: %s", base_url, exc)
        return False
    
    api = ApiMethods(credentials, base_url)
    sceneManager = SceneManager(api)
    
    async def async_update_data():
        """Fetch data from API endpoint."""
        roomData = await hass.async_add_executor_job(api.getRoomsList)
        return roomData

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="climate",
        update_method=async_update_data,
        update_interval=datetime.timedelta(seconds=2),
    )
    
    await coordinator.async_refresh()    
    
    async_add_entities(
        HeatAppClimateEntity(coordinator, heatapproom, api, sceneManager) for heatapproom, ent in enumerate(coordinator.data)
    ) 
  
async def async_setup_entry(hass: HomeAssistant, config_entry: config_entries.ConfigEntry, async_add_entities: AddEntitiesCallback):
    hass.async_create_task(async_setup_integration(hass, config_entry, async_add_entities))


class HeatAppClimateEntity(CoordinatorEntity, ClimateEntity):
    """Representation of a HeatApp Thermostat device."""

    def __init__(self, coordinator, heatappRoomData, apiObject, scene):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.idx = heatappRoomData
        self._apiObject = apiObject
        self._sceneManager = scene
        self._activeMode = HVACMode.OFF
        self._activePreset = PRESET_NONE
        _LOGGER.info("initializing thermostat: %s", self.idx)
        
        try:
            _LOGGER.info("data: %s", self.coordinator.data[self.idx])
        except (IndexError, KeyError, TypeError):
            _LOGGER.warning("Coordinator data unavailable during initialization for index %s", self.idx)

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
            self._apiObject.getSwitchingTimes, self.coordinator.data[self.idx]["data"]["name"], self.coordinator.data[self.idx]["data"]["id"]
        )

    def getTodaysSchedule(self):
        if getattr(self, "_schedulePeriodsForRoom", None) and self._schedulePeriodsForRoom.get("success"):            
            weekDayIndex = datetime.datetime.now().weekday()
            listStartIndex = weekDayIndex * 3
            return self._schedulePeriodsForRoom["switchingtimes"][listStartIndex:listStartIndex+3]
        return None

    @property
    def unique_id(self):
        """Return a unique ID."""
        try:
            return self.coordinator.data[self.idx]["name"]
        except (IndexError, KeyError, TypeError):
            return f"heatapp_idx_{self.idx}"

    @property
    def name(self):
        """Return the name of the entity."""
        try:
            return self.coordinator.data[self.idx]["name"]
        except (IndexError, KeyError, TypeError):
            return f"HeatApp Zone {self.idx}"

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "HeatApp (danfoss)",
        }

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return UnitOfTemperature.CELSIUS

    @property
    def target_temperature(self):
        """Return the target temperature."""
        try:
            desired = self.coordinator.data[self.idx]["data"]["desiredTemperature"]
            return float(desired) if desired is not None else None
        except (IndexError, KeyError, TypeError, ValueError):
            return None

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 0.5

    @property
    def current_temperature(self):
        """Return the current temperature."""
        try:
            actual = self.coordinator.data[self.idx]["data"]["actualTemperature"]
            return float(actual) if actual is not None else None
        except (IndexError, KeyError, TypeError, ValueError):
            return None

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        try:
            return float(self.coordinator.data[self.idx]["data"]["minTemperature"])
        except (IndexError, KeyError, TypeError, ValueError):
            return 5.0

    @property
    def max_temp(self):
        """Return the maximum temperature."""
