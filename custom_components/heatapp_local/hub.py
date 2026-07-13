from heatapp.apiMethods import ApiMethods
from heatapp.login import Login
from heatapp.sceneManager import SceneManager
from homeassistant.core import HomeAssistant
import threading
from collections import OrderedDict

import logging

_LOGGER = logging.getLogger(__name__)

class HeatappHub:
    def __init__(self, hass: HomeAssistant, host: str, user: str, password: str) -> None:
        """Initialize."""
        self.host = host
        self.user = user
        self.password = password
        
        # Ensure 'http://' is only added if not already present, 
        # and ensure we are using the sanitized host passed from __init__.py
        base_url = self.host if self.host.startswith("http") else f"http://{self.host}"
        
        loginManager = Login(base_url)
        # Using executor job for blocking library calls is correct
        credentials = hass.async_add_executor_job(loginManager.authorize, self.user, self.password)
        
        api = ApiMethods(credentials, base_url)
        sceneManager = SceneManager(api)
        self._lock = threading.Lock()
