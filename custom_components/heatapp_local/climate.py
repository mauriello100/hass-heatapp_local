"""Platform for climate integration."""
from __future__ import annotations

import datetime
import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
_LOGGER = logging.getLogger(__name__)

PRESET_NONE = "None"
PRESET_BOOST = "Boost"
PRESET_HOLIDAY = "Holiday"
PRESET_GO = "Leave"
PRESET_PARTY = "Party"
PRESET_STANDBY = "Standby"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up heatapp climate entities from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Coordinator data is pre-populated by async_config_entry_first_refresh in __init__.py
    async_add_entities(
        HeatAppClimateEntity(coordinator, idx) 
        for idx, _ in enumerate(coordinator.data)
    )


class HeatAppClimateEntity(CoordinatorEntity, ClimateEntity):
    """Representation of a HeatApp Thermostat device."""

    def __init__(self, coordinator, heatapp_room_idx: int) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.idx = heatapp_room_idx
        self._activeMode = ""
        self._activePreset = PRESET_NONE
        self._schedulePeriodsForRoom = {"success": False}
        _LOGGER.info("Initializing heatapp thermostat entity index: %s", self.idx)

    async def async_added_to_hass(self) -> None:
        """Run tasks when entity is added to registry."""
        await super().async_added_to_hass() 
        try: 
            await self.initOneTimeInformation()
        except Exception as exc: 
            _LOGGER.warning(
                "Failed to fetch switching times for %s: %s", 
                self.coordinator.data[self.idx]["name"], exc
            ) 
            
    async def initOneTimeInformation(self) -> None:
        """Fetch historical scheduling details."""
        self._schedulePeriodsForRoom = await self.hass.async_add_executor_job(
            self.coordinator.api.api.getSwitchingTimes, 
            self.coordinator.data[self.idx]["data"]["name"], 
            self.coordinator.data[self.idx]["data"]["id"]
        )

    def getTodaysSchedule(self) -> list | None:
        """Extract current day metrics from switching schedule."""
        if getattr(self, "_schedulePeriodsForRoom", None) and self._schedulePeriodsForRoom.get("success"):            
            weekDayIndex = datetime.datetime.now().weekday()
            listStartIndex = weekDayIndex * 3
            return self._schedulePeriodsForRoom["switchingtimes"][listStartIndex:listStartIndex+3]
        return None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.coordinator.data[self.idx]["name"]

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self.coordinator.data[self.idx]["name"]

    @property
    def device_info(self) -> dict:
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.coordinator.data[self.idx]["name"],
            "manufacturer": "HeatApp (Danfoss)",
        }

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def target_temperature(self) -> float:
        """Return the target temperature."""
        return self.coordinator.data[self.idx]["data"]["desiredTemperature"]

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return 0.5

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self.coordinator.data[self.idx]["data"]["actualTemperature"]

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self.coordinator.data[self.idx]["data"]["minTemperature"]

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.coordinator.data[self.idx]["data"]["maxTemperature"]

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        return [HVACMode.HEAT, HVACMode.OFF, HVACMode.AUTO, HVACMode.COOL]  

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode."""
        self.determine_preset_membership()
        return self._activePreset

    @property
    def preset_modes(self) -> list[str]:
        """Return available presets."""
        return [PRESET_NONE, PRESET_BOOST, PRESET_HOLIDAY, PRESET_GO, PRESET_PARTY, PRESET_STANDBY]

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode."""
        self.determine_mode_membership()
        return self._activeMode

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode via the scene manager context."""
        room_id = self.coordinator.data[self.idx]["data"]["id"]
        scene_mgr = self.coordinator.api.scene_manager

        if self._activePreset != "" and preset_mode != self._activePreset:
            if self._activePreset != PRESET_NONE:
                await self.hass.async_add_executor_job(
                    scene_mgr.removeMemberFromScene, room_id, self._activePreset, True
                )
            
            if preset_mode != PRESET_NONE:
                await self.hass.async_add_executor_job(
                    scene_mgr.addMemberToScene, room_id, preset_mode, True
                )
            
            self._activePreset = preset_mode
            await self.coordinator.async_request_refresh()

    def is_between_obj(self, time, range_start, range_end) -> bool:
        """Helper to parse and evaluate schedule hours boundaries."""
        time_format = '%H:%M'
        range_start = datetime.datetime.strptime(range_start, time_format).time()
        range_end = datetime.datetime.strptime(range_end, time_format).time()
        return (range_start <= time <= range_end) or (
            range_end <= range_start and (range_start <= time or time <= range_end)
        )

    def determine_preset_membership(self) -> None:
        """Process status variables into matching HA entity presets."""
        roomstatus = self.coordinator.data[self.idx]["data"]["roomstatus"]
        
        if roomstatus == 43:
            self._activePreset = PRESET_PARTY
        elif roomstatus == 99:    
            _LOGGER.warning("Room %s reports active problem status flag", self.coordinator.data[self.idx]["name"])
        elif roomstatus == 127:
            self._activePreset = PRESET_HOLIDAY
        elif roomstatus == 132:
            self._activePreset = PRESET_STANDBY
        elif roomstatus == 130:
            self._activePreset = PRESET_GO
        elif roomstatus == 46:
            self._activePreset = PRESET_BOOST
        elif roomstatus in [41, 51, 54, 122, 131, 137]:
            self._activePreset = PRESET_NONE
        else:
            _LOGGER.warning("Unknown status code %s encountered on room %s", roomstatus, self.coordinator.data[self.idx]["data"]["name"])
            self._activePreset = PRESET_NONE

    def determine_mode_membership(self) -> None:
        """Evaluate operational heating flags based on temperature differentials."""
        actual_temp = self.coordinator.data[self.idx]["data"]["actualTemperature"]
        target_temp = self.coordinator.data[self.idx]["data"]["desiredTemperature"]

        if self._activePreset == PRESET_NONE:
            if actual_temp < target_temp:
                self._activeMode = HVACMode.HEAT
            elif actual_temp > target_temp:
                self._activeMode = HVACMode.COOL
            else:
                self._activeMode = HVACMode.OFF
        elif self._activePreset in [PRESET_PARTY, PRESET_BOOST]:
            self._activeMode = HVACMode.HEAT 
        else:
            self._activeMode = HVACMode.OFF
        
    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.hass.async_add_executor_job(
            self.coordinator.api.api.setTemp, temperature, self.coordinator.data[self.idx]["data"]["id"]
        )
        await self.coordinator.async_request_refresh()

    async def turn_on(self, **kwargs) -> None: 
        """Turn entity execution on."""
        if self._activePreset in [PRESET_BOOST, PRESET_NONE]:
            return
        
        await self.hass.async_add_executor_job(
            self.coordinator.api.scene_manager.removeMemberFromScene, 
            self.coordinator.data[self.idx]["data"]["id"], self._activePreset, True
        )
        await self.coordinator.async_request_refresh()

    async def turn_off(self, **kwargs) -> None:
        """Force device into tracking standby configuration."""
        if self._activePreset in [PRESET_GO, PRESET_HOLIDAY, PRESET_STANDBY]:
            return
        await self.hass.async_add_executor_job(
            self.coordinator.api.scene_manager.addMemberToScene, 
            self.coordinator.data[self.idx]["data"]["id"], "Standby", True
        )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set target operational runtime environment mode mapping."""
        if hvac_mode == HVACMode.HEAT:
            await self.turn_on()
        elif hvac_mode == HVACMode.OFF:
            await self.turn_off()
