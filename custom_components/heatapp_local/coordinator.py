from __future__ import annotations
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .hub import HeatappHub
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# coordinator.py

class heatAppDeviceUpdateCoordinator(DataUpdateCoordinator):
    """Gather data for the energy device."""

    def __init__(self, hass, host, user, password, interval) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=interval),
        )
        self.api = HeatappHub(hass, host, user, password)
        self.interval = interval

    async def _async_update_data(self) -> dict:
        """Update data via coordinator."""
        try:
            # Lazy authentication: only authenticate if not already done
            if self.api.api is None:
                await self.api.authenticate()
            
            # Now you can safely use self.api.api to fetch data
            # Example: return await self.hass.async_add_executor_job(self.api.api.getData)
            return {} 
            
        except Exception as err:
            _LOGGER.error("Error communicating with API: %r", err)
            raise UpdateFailed(f"Error communicating with API: {err}")
