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
        """Initialize the Hub. No blocking network calls occur here."""
        self.hass = hass
        self.host = host  # Already normalized via config_flow.py
        self.user = user
        self.password = password
        self._lock = threading.Lock()
        
        self.login_manager = Login(self.host)
        self.api = None
        self.scene_manager = None

    def fetch_data_sync(self) -> list:
        """Synchronously initialize the API and fetch data (must run in executor)."""
        with self._lock:
            # Only authenticate and instantiate objects once per session
            if self.api is None or self.scene_manager is None:
                # This blocking call is safe because the coordinator runs it in an executor job
                credentials = self.login_manager.authorize(self.user, self.password)
                self.api = ApiMethods(credentials, self.host)
                self.scene_manager = SceneManager(self.api)
            
            # --- API DATA FETCHING ---
            # Fetch the rooms/zones from the Heatapp system.
            # CHANGE `getRooms()` TO THE ACTUAL METHOD EXPOSED BY YOUR API WRAPPER
            try:
                raw_rooms = self.api.getRooms() 
            except AttributeError:
                _LOGGER.error("Method to fetch rooms not found. Please update hub.py with the correct heatapp method.")
                return []
            
            # Restructure the raw data into the format expected by climate.py
            formatted_data = []
            for room in raw_rooms:
                formatted_data.append({
                    "name": room.get("name", "Unknown Room"),
                    "data": room
                })
                
            return formatted_data
