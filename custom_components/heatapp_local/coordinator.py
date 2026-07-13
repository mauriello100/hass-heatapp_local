from __future__ import annotations
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .hub import HeatappHub
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class heatAppDeviceUpdateCoordinator(DataUpdateCoordinator):
    """Gather data for the energy device."""

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
        # Store configuration for lazy authentication
        self.host = host
        self.user = user
        self.password = password
        self.api = HeatappHub(hass, host, user, password)

    async def _async_update_data(self) -> dict:
        """Update data via coordinator."""
        try:
            # Check if the hub is authenticated. 
            # If self.api.api is None, we need to authenticate first.
            if self.api.api is None:
                _LOGGER.debug("Authenticating with HeatApp hub...")
                await self.api.authenticate()
            
            # Now that self.api.api is initialized, perform your data fetch.
            # Example:
            # data = await self.hass.async_add_executor_job(self.api.api.get_data)
            # return data
            
            _LOGGER.debug("Data update successful")
            return {"status": "success"} # Replace with your actual fetched data
            
        except Exception as err:
            _LOGGER.error("Error communicating with HeatApp: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}")
