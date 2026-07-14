from heatapp.apiMethods import ApiMethods
from heatapp.login import Login
from heatapp.sceneManager import SceneManager
from homeassistant.core import HomeAssistant
import threading
from collections import OrderedDict

import logging

_LOGGER = logging.getLogger(__name__)

# hub.py
class HeatappHub:
    def __init__(self, hass, host, user, password) -> None:
        self.host = host
        self.user = user
        self.password = password
        self.api = None # Initialize as None
        self._lock = threading.Lock()

    def get_all_data(self):
        """Thread-safe method called by the coordinator."""
        with self._lock:
            if self.api is None:
                # Perform the blocking auth here, inside the thread
                loginManager = Login("http://" + self.host)
                credentials = loginManager.authorize(self.user, self.password)
                self.api = ApiMethods(credentials, "http://" + self.host)
            
            # Return the actual data
            return self.api.get_data()
