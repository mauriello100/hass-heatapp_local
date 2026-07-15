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
        self._activeMode = ""
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
            _LOGGER.debug("the current temperature in coordinator data is: %s", desired)
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
            return 5.0  # Safe thermostat baseline fallback

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        try:
            return float(self.coordinator.data[self.idx]["data"]["maxTemperature"])
        except (IndexError, KeyError, TypeError, ValueError):
            return 30.0  # Safe thermostat upper fallback

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return [HVACMode.HEAT, HVACMode.OFF, HVACMode.AUTO, HVACMode.COOL]  

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        self.determine_preset_membership()
        return self._activePreset
        
    async def async_set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        try:
            room_id = self.coordinator.data[self.idx]["data"]["id"]
            room_name = self.coordinator.data[self.idx]["name"]
        except (IndexError, KeyError, TypeError):
            _LOGGER.error("Cannot set preset mode; room identity data is missing for index %s", self.idx)
            return

        _LOGGER.info("preset_mode to enable is: %s", preset_mode)
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
        _LOGGER.info("Scene adjustment finished for room: %s", room_name)

    @property
    def preset_modes(self):
        return [PRESET_NONE, PRESET_BOOST, PRESET_HOLIDAY, PRESET_GO, PRESET_PARTY, PRESET_STANDBY]

    @property
    def hvac_mode(self):
        """Return current operation."""
        self.determine_if_device_is_following_schema()
        self.determine_mode_membership()
        return self._activeMode

    def is_between(self, time, time_range):
        if time_range[1] < time_range[0]:
            return time >= time_range[0] or time <= time_range[1]
        return time_range[0] <= time <= time_range[1]
    
    def is_between_obj(self, time, range_start, range_end):
        time_format = '%H:%M'
        try:
            range_start = datetime.datetime.strptime(range_start, time_format).time()
            range_end = datetime.datetime.strptime(range_end, time_format).time()
            return (range_start <= time <= range_end) or (
                range_end <= range_start and (range_start <= time or time <= range_end)
            )
        except (ValueError, TypeError):
            return False

    def determine_if_device_is_following_schema(self):
        currentTime = datetime.datetime.now().time()
        schedulePeriodsToday = self.getTodaysSchedule()
        
        desiredTempDaySchedule = None
        desiredTempDay2Schedule = None
        desiredTempNightSchedule = None

        if schedulePeriodsToday is not None: 
            desiredTempDaySchedule = next((elem for elem in schedulePeriodsToday if elem is not None and elem.get("type") == "H"), None)
            desiredTempDay2Schedule = next((elem for elem in schedulePeriodsToday if elem is not None and elem.get("type") == "L"), None)
            desiredTempNightSchedule = next((elem for elem in schedulePeriodsToday if elem is not None and elem.get("type") == "N"), None)
        else:
            _LOGGER.debug("Unable to retrieve the schedule periods for today for index %s", self.idx)

        if desiredTempDaySchedule is not None and "from" in desiredTempDaySchedule and "to" in desiredTempDaySchedule:
            if self.is_between_obj(currentTime, desiredTempDaySchedule["from"], desiredTempDaySchedule["to"]):
                return "Day"

        if desiredTempDay2Schedule is not None and "from" in desiredTempDay2Schedule and "to" in desiredTempDay2Schedule:
            if self.is_between_obj(currentTime, desiredTempDay2Schedule["from"], desiredTempDay2Schedule["to"]):
                return "Evening"

        if desiredTempNightSchedule is not None and "from" in desiredTempNightSchedule and "to" in desiredTempNightSchedule:
            if self.is_between_obj(currentTime, desiredTempNightSchedule["from"], desiredTempNightSchedule["to"]):
                return "Night"

        return "Manual"

    def determine_preset_membership(self):
        try:
            roomstatus = self.coordinator.data[self.idx]["data"]["roomstatus"]
