"""Heatapp API client wrapper."""
import logging
import threading

from heatapp.apiMethods import ApiMethods
from heatapp.login import Login
from heatapp.sceneManager import SceneManager
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class HeatappHub:
    """A thread-safe wrapper around the synchronous heatapp API library."""

    def __init__(self, hass: HomeAssistant, host: str, user: str, password: str) -> None:
        """Initialize the hub reference."""
        self.hass = hass
        self.host = host
        self.user = user
        self.password = password
        
        # Initialized lazily via authenticate()
        self.api = None
        self.scene_manager = None
        self._lock = threading.Lock()

    def authenticate(self) -> None:
        """Authenticate against the HeatApp endpoint. 
        
        Must be executed within hass.async_add_executor_job.
        """
        with self._lock:
            if self.api is not None:
                return  # Already authenticated
            
            _LOGGER.info("Authenticating against HeatApp host: %s", self.host)
            login_manager = Login(self.host)
            credentials = login_manager.authorize(self.user, self.password)
            
            self.api = ApiMethods(credentials, self.host)
            self.scene_manager = SceneManager(self.api)
