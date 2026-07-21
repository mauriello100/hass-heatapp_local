"""Hub for Heatapp Local."""
from __future__ import annotations

import logging
import threading
from http.client import RemoteDisconnected

import requests

from heatapp.apiMethods import ApiMethods
from heatapp.login import Login
from heatapp.sceneManager import SceneManager
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

class HeatappHub:
    """Wrapper class to handle Heatapp API communication."""

    def __init__(self, hass: HomeAssistant, host: str, user: str, password: str) -> None:
        """Initialize the Hub[cite: 15]."""
        self.hass = hass
        self.host = host
        self.user = user
        self.password = password
        self._lock = threading.Lock()
        
        self.login_manager = Login(self.host)[cite: 15]
        self.api = None
        self.scene_manager = None

    def fetch_data_sync(self) -> list:
        """Synchronously initialize the API and fetch data with auto-reauthentication."""
        with self._lock:
            # Initialize API only if not already done or if session was invalidated
            if self.api is None or self.scene_manager is None:
                try:
                    credentials = self.login_manager.authorize(self.user, self.password)[cite: 15]
                    self.api = ApiMethods(credentials, self.host)[cite: 15]
                    self.scene_manager = SceneManager(self.api)[cite: 15]
                except Exception as e:
                    _LOGGER.error("Failed to authenticate or initialize API: %s", e)[cite: 15]
                    self.api = None
                    self.scene_manager = None
                    return []

            # --- API DATA FETCHING ---
            try:
                raw_rooms = self.api.getRoomsList()[cite: 15]
                
                if not raw_rooms:
                    _LOGGER.debug("API returned no data.")[cite: 15]
                    return []

                # Restructure the raw data into the format expected by climate.py[cite: 15]
                formatted_data = []

                # Scenario 1: API returns a direct list (e.g., [{}, {}])[cite: 15]
                if isinstance(raw_rooms, list):
                    for room in raw_rooms:
                        formatted_data.append({
                            "name": room.get("name", "Unknown Room"),
                            "data": room
                        })
                
                # Scenario 2: API returns a dictionary (e.g., {'rooms': [{}, {}]})[cite: 15]
                elif isinstance(raw_rooms, dict):
                    rooms_list = raw_rooms.get("rooms") or raw_rooms.get("roomList") or []
                    for room in rooms_list:
                        formatted_data.append({
                            "name": room.get("name", "Unknown Room"),
                            "data": room
                        })
                
                return formatted_data

            except (RemoteDisconnected, requests.exceptions.RequestException) as e:
                _LOGGER.warning("Connection lost or dropped by Heatapp device, resetting session: %s", e)
                # Invalidate session so it triggers a fresh login token challenge on the next poll
                self.api = None
                self.scene_manager = None
                return []
            except AttributeError:
                _LOGGER.error("Method `getRoomsList` encountered an error or does not exist.")[cite: 15]
                return []
            except Exception as e:
                _LOGGER.error("Unexpected error fetching data: %s", e)[cite: 15]
                return []
