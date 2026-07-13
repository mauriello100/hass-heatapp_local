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
        self.hass = hass
        self.host = host
        self.user = user
        self.password = password
        self.api = None
        self._lock = threading.Lock()

    async def authenticate(self):
        """Perform asynchronous authentication."""
        base_url = self.host if self.host.startswith("http") else f"http://{self.host}"
        loginManager = Login(base_url)
        
        # PROPERLY AWAIT the executor job
        credentials = await self.hass.async_add_executor_job(
            loginManager.authorize, self.user, self.password
        )
        
        self.api = ApiMethods(credentials, base_url)
        # Initialize other managers here if needed
