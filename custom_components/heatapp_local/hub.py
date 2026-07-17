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

    def fetch_data_sync(self) -> dict:
        """Synchronously initialize the API and fetch data (must run in executor)."""
        with self._lock:
            # Only authenticate and instantiate objects once per session
            if self.api is None or self.scene_manager is None:
                # This blocking call is safe because the coordinator runs it in an executor job
                credentials = self.login_manager.authorize(self.user, self.password)
                self.api = ApiMethods(credentials, self.host)
                self.scene_manager = SceneManager(self.api)
            
            # --- API DATA FETCHING ---
            # TODO: Call your scene_manager methods here to grab the actual climate data.
            # Example: data = self.scene_manager.get_system_state()
            
            # We return a dummy dict for now so coordinator.data is truthy during testing.
            # Replace this dict with your actual return data object.
            return {"status": "connected"}
