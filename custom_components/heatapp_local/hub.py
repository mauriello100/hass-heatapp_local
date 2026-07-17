"""Hub for Heatapp Local."""
import logging
import threading

from heatapp.apiMethods import ApiMethods
from heatapp.login import Login
from heatapp.sceneManager import SceneManager
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

class HeatappHub:
    """Wrapper class to handle Heatapp API communication."""

    def __init__(self, hass: HomeAssistant, host: str, user: str, password: str) -> None:
        """Initialize the Hub."""
        self.hass = hass
        self.host = host
        self.user = user
        self.password = password
        self._lock = threading.Lock()
        
        self.login_manager = Login(self.host)
        self.api = None
        self.scene_manager = None

    def fetch_data_sync(self) -> list:
        """Synchronously initialize the API and fetch data."""
        with self._lock:
            if self.api is None or self.scene_manager is None:
                credentials = self.login_manager.authorize(self.user, self.password)
                self.api = ApiMethods(credentials, self.host)
                self.scene_manager = SceneManager(self.api)
                
                # --- DEBUGGING: Log all available methods ---
                _LOGGER.info("DEBUG: Available API methods: %s", dir(self.api))
            
            # --- API DATA FETCHING ---
            try:
                # We are testing the API object here.
                # If this fails again, check the logs for the 'DEBUG' line.
                raw_rooms = self.api.getRooms() 
            except AttributeError:
                _LOGGER.error("Method `getRooms` not found. Please check the logs for the `DEBUG: Available API methods` list to find the correct one.")
                return []
            
            # Restructure the raw data into the format expected by climate.py
            formatted_data = []
            for room in raw_rooms:
                formatted_data.append({
                    "name": room.get("name", "Unknown Room"),
                    "data": room
                })
                
            return formatted_data
