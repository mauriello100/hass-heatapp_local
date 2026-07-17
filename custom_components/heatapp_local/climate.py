from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from .const import CONF_USER, CONF_PASSWORD, CONF_HOST, DOMAIN
from heatapp.apiMethods import ApiMethods
from heatapp.login import Login
from heatapp.sceneManager import SceneManager
from homeassistant import config_entries
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)

import datetime
import logging

from homeassistant.helpers.update_coordinator import CoordinatorEntity

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE

_LOGGER = logging.getLogger(__name__)

PRESET_NONE = "None"
PRESET_BOOST = "Boost"
PRESET_HOLIDAY = "Holiday"
PRESET_GO = "Leave"
PRESET_PARTY = "Party"
PRESET_STANDBY = "Standby"

def _normalize_base_url(host: str) -> str:
    host = (str(host) or "").strip()
    if host.startswith(("http://", "https://")):
        return host.rstrip("/")
    return f"http://{host}".rstrip("/")

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    # Use the coordinator created in __init__.py
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    if not coordinator.data:
        # __init__ should ensure this, but keep a defensive guard
        raise ConfigEntryNotReady("HeatApp returned no data during initial setup")

    # Build base_url and login once for command APIs
    base_url = _normalize_base_url(config_entry.data[CONF_HOST])
    login_manager = Login(base_url)
    try:
        credentials = await hass.async_add_executor_job(
            login_manager.authorize,
            config_entry.data[CONF_USER],
            config_entry.data[CONF_PASSWORD],
        )
    except Exception as exc:
        # Do not proceed without credentials; let HA retry later
        raise ConfigEntryNotReady(f"Authorization failed against {base_url}: {exc}") from exc

    api = ApiMethods(credentials, base_url)
    scene_manager = SceneManager(api)

    rooms = coordinator.data
    if not isinstance(rooms, (list, tuple)) or len(rooms) == 0:
        raise ConfigEntryNotReady("No rooms returned from HeatApp during initial setup")

    entities = [
        HeatAppClimateEntity(coordinator, idx, api, scene_manager)
        for idx in range(len(rooms))
    ]
    async_add_entities(entities)

class HeatAppClimateEntity(CoordinatorEntity, ClimateEntity):
    """Representation of a HeatApp Thermostat device."""

    def __init__(self, coordinator, room_index: int, apiObject, scene):
        super().__init__(coordinator)
        self.idx = room_index
        self._apiObject = apiObject
        self._sceneManager = scene
        self._activeMode = ""
        self._activePreset = PRESET_NONE
        # Reduce log noise: switch to debug if needed
        _LOGGER.debug("Initializing thermostat index: %s", self.idx)

    def _room(self):
        rooms = self.coordinator.data or []
        if 0 <= self.idx < len(rooms):
            return rooms[self.idx]
        return {}

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        try:
            await self.initOneTimeInformation()
        except Exception as exc:
            room = self._room()
            _LOGGER.warning("Failed to fetch switching times for %s: %s", room.get("name"), exc)
            self._schedulePeriodsForRoom = {"success": False}

    async def initOneTimeInformation(self):
        room = self._room()
        self._schedulePeriodsForRoom = await self.hass.async_add_executor_job(
            self._apiObject.getSwitchingTimes, room["data"]["name"], room["data"]["id"]
        )

    @property
    def unique_id(self):
        room = self._room()
        # Prefer stable numeric/device id, not the room name
        return str(room["data"]["id"])

    @property
    def name(self):
        room = self._room()
        return room.get("name")

    @property
    def device_info(self):
        room = self._room()
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": room.get("name"),
            "manufacturer": "HeatApp (Danfoss)",
        }

    @property
    def temperature_unit(self):
        return UnitOfTemperature.CELSIUS

    @property
    def target_temperature(self):
        room = self._room()
        return room["data"]["desiredTemperature"]

    @property
    def target_temperature_step(self):
        return 0.5

    @property
    def current_temperature(self):
        room = self._room()
        return room["data"]["actualTemperature"]

    @property
    def min_temp(self):
        room = self._room()
        return room["data"]["minTemperature"]

    @property
    def max_temp(self):
        room = self._room()
        return room["data"]["maxTemperature"]

    @property
    def supported_features(self):
        return SUPPORT_FLAGS

    @property
    def hvac_modes(self):
        return [HVACMode.HEAT, HVACMode.OFF, HVACMode.AUTO, HVACMode.COOL]

    @property
    def preset_mode(self):
        self.determine_preset_membership()
        return self._activePreset


    def determine_preset_membership(self):
#        roomstatus = self._data["data"]["roomstatus"]
        roomstatus = self.coordinator.data[self.idx]["data"]["roomstatus"]
#        _LOGGER.info("Room name: %s has status", self._data["data"]["originalName"])
#        _LOGGER.info("code: %s ", self._data["data"]["roomstatus"] )
        if roomstatus == 43:
            
            self._activePreset = PRESET_PARTY
            _LOGGER.info("room has party mode active as scene for room: %s", self.coordinator.data[self.idx]["data"]["id"])
        elif roomstatus == 99:    
            _LOGGER.info("room has an problem active: %s", self.coordinator.data[self.idx]["data"]["originalName"])
        elif roomstatus == 127:
            self._activePreset = PRESET_HOLIDAY
        elif roomstatus == 132:
            self._activePreset = PRESET_STANDBY
        elif roomstatus == 130:
            self._activePreset = PRESET_GO
        elif roomstatus == 46:
            self._activePreset = PRESET_BOOST
        elif roomstatus == 122 or roomstatus == 51 or roomstatus == 41 or roomstatus == 131 or roomstatus == 54 or roomstatus == 137:
            #status code 54 hasn't positively been mapped to an scene however it appears to be linked being on or around the correct set temp
            #122 work according to schema, 51 user manually set an desired temp heating while 41 is used to define that the set temp would entail cooling
            #131 is used to indicate that the minimal normal (non scene) temp was manually set
            #137 seems to indicate that the outside and room temp is above the set value for that room
            self._activePreset = PRESET_NONE
            _LOGGER.info("Room has manual / schema mode active as scene for room %s", self.coordinator.data[self.idx]["data"]["id"])
        else:
            _LOGGER.warning("The room %s has entered an unknown preset please inform the developer (give the dev the following code %s). This will default to the none preset until fixed", self.coordinator.data[self.idx]["data"]["name"], roomstatus)
            self._activePreset = PRESET_NONE
#        _LOGGER.info("active scene %s", self._activeMode)
#        boostMember = self._sceneManager.isMemberOfScene(roomId, PRESET_BOOST)
#        if boostMember == True:
#            return 


# HVACMode.HEAT,HVACMode.OFF,HVACMode.AUTO,HVACMode.COOL
    def determine_mode_membership(self):
        _LOGGER.info("active scene %s", self._activeMode)
        if self._activePreset == PRESET_NONE:
            if self.coordinator.data[self.idx]["data"]["actualTemperature"] < self.coordinator.data[self.idx]["data"]["desiredTemperature"]:
                self._activeMode = HVACMode.HEAT
            elif self.coordinator.data[self.idx]["data"]["actualTemperature"] > self.coordinator.data[self.idx]["data"]["desiredTemperature"]:
                self._activeMode = HVACMode.COOL
            elif self.coordinator.data[self.idx]["data"]["actualTemperature"] == self.coordinator.data[self.idx]["data"]["desiredTemperature"]:
                self._activeMode = HVACMode.OFF
            
        elif self._activePreset == PRESET_PARTY:
            self._activeMode = HVACMode.HEAT 

        elif self._activePreset == PRESET_HOLIDAY:
            self._activeMode = HVACMode.OFF
            
        elif self._activePreset == PRESET_GO:
            self._activeMode = HVACMode.OFF
            
        elif self._activePreset == PRESET_STANDBY:
            self._activeMode = HVACMode.OFF
            
        elif self._activePreset == PRESET_BOOST:
            self._activeMode = HVACMode.HEAT
        
        
    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.hass.async_add_executor_job(
            self._apiObject.setTemp, temperature, self.coordinator.data[self.idx]["data"]["id"]
        )
        #self.coordinator.data[self.idx]["data"]["desiredTemperature"] = temperature
#    async def async_set_preset_mode(self, **kwargs):
        """Set new preset mode."""
        #return BOOST
        
    async def turn_on(self, **kwargs): 
        if self._activePreset == PRESET_BOOST or self._activePreset == PRESET_NONE: #should be based on temp whether something should be done
            return
        
        await self.hass.async_add_executor_job(
            self._sceneManager.removeMemberFromScene, self.coordinator.data[self.idx]["data"]["id"], self._activePreset, True
        )
        self.determine_mode_membership()

    async def turn_off(self, **kwargs):
        if self._activePreset == PRESET_GO or self._activePreset == PRESET_HOLIDAY or self._activePreset == PRESET_STANDBY: #should be based on temp whether something should be done
            return
        await self.hass.async_add_executor_job(
            self._sceneManager.addMemberToScene, self.coordinator.data[self.idx]["data"]["id"], "Standby", True
        )
        self.determine_mode_membership()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.HEAT:
            await self.turn_on()
            return
        if hvac_mode == HVACMode.OFF:
            await self.turn_off()
            
#    async def async_update(self):
#        """Retrieve latest state."""
#        result = await self.hass.async_add_executor_job(
#            self._apiObject.getSpecificRoom, self._data["data"]["id"]
#        )
#        #_LOGGER.info("update data obj: %s", result)
#        self._data = result
#        
#        self.hass.async_add_executor_job(self.determine_mode_membership, self._data["data"]["id"])
#        self.hass.async_add_executor_job(self.determine_preset_membership, self._data["data"]["id"])
#        _LOGGER.info("the active scene is: %s", self._activeMode)

#        return
        #try:
        #    token_info = await self._heater.control.refresh_access_token()
        #except ambiclimate.AmbiclimateOauthError:
        #    _LOGGER.error("Failed to refresh access token")
        #    return

        #if token_info:
        #    await self._store.async_save(token_info)

        #self._data = await self._heater.update_device()
