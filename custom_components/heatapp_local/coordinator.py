"""DataUpdateCoordinator for the heatapp_local integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .hub import HeatappHub

_LOGGER = logging.getLogger(__name__)


class heatAppDeviceUpdateCoordinator(DataUpdateCoordinator):
    """Gather data centrally for all HeatApp climate entities."""

    api: HeatappHub
   
    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        user: str,
        password: str,
        interval: int,
    ) -> None:
        """Initialize Update Coordinator."""
        super().__init__(
            hass, 
            _LOGGER, 
            name=DOMAIN, 
            update_interval=timedelta(seconds=interval),
        )
        self.api = HeatappHub(hass, host, user, password)
        self.interval = interval

    async def _async_update_data(self) -> list:
        """Fetch data from HeatApp endpoint."""
        try:
            # 1. Ensure the hub wrapper has established authenticated sessions
            if self.api.api is None:
                await self.hass.async_add_executor_job(self.api.authenticate)
            
            # 2. Fetch data via the synchronous backend library
            room_data = await self.hass.async_add_executor_job(self.api.api.getRoomsList)
            
            if not room_data:
                raise UpdateFailed("HeatApp instance returned empty or invalid room data")
                
            return room_data

        except Exception as err:
            raise UpdateFailed(f"Error communicating with HeatApp API: {err}") from err
