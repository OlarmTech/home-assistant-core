"""The coordinator for the olarm integration to handle API and MQTT connections."""

from __future__ import annotations

import asyncio
import logging
import ssl
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientResponseError
from olarmflowclient import OlarmFlowClient, OlarmFlowClientApiError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class OlarmDeviceData:
    """Data structure to hold Olarm device information."""

    device_name: str
    device_state: dict[str, Any] | None = None
    device_links: dict[str, Any] | None = None
    device_io: dict[str, Any] | None = None
    device_profile: dict[str, Any] | None = None
    device_profile_links: dict[str, Any] | None = None
    device_profile_io: dict[str, Any] | None = None


class OlarmDataUpdateCoordinator(DataUpdateCoordinator[OlarmDeviceData]):
    """Manages an individual olarms config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
        olarm_client: OlarmFlowClient,
    ) -> None:
        """Create a new instance of the OlarmCoordinator."""

        self._oauth_session = oauth_session

        # user props
        self._user_id = entry.data["user_id"]

        # device props
        self.device_id = entry.data["device_id"]

        # olarm connect client
        self._olarm_connect_client = olarm_client

        # Initialize DataUpdateCoordinator with no update interval (one-time setup only)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{self.device_id}",
            update_interval=None,  # No periodic updates, MQTT handles ongoing updates
        )

    async def _async_update_data(self) -> OlarmDeviceData:
        """Fetch device information from the Olarm API."""
        try:
            device = await self._olarm_connect_client.get_device(self.device_id)

            _LOGGER.debug("Device -> %s", device)

            device_name = device.get("deviceName") or f"Olarm Device {self.device_id}"

            device_data = OlarmDeviceData(
                device_name=device_name,
                device_state=device.get("deviceState"),
                device_links=device.get("deviceLinks"),
                device_io=device.get("deviceIO"),
                device_profile=device.get("deviceProfile"),
                device_profile_links=device.get("deviceProfileLinks"),
                device_profile_io=device.get("deviceProfileIO"),
            )

            _LOGGER.debug(
                "Device -> %s",
                {
                    "device_name": device_data.device_name,
                    "device_state": device_data.device_state,
                },
            )

            return device_data

        except OlarmFlowClientApiError as e:
            raise UpdateFailed("Failed to reach Olarm API") from e

    def _update_coordinator_data(self):
        """Update coordinator data when properties change."""
        if self.data:
            # Update the coordinator with the current data
            self.async_set_updated_data(self.data)

    # Settable properties for backward compatibility with MQTT updates
    @property
    def device_name(self) -> str:
        """Return the device name."""
        return self.data.device_name if self.data else f"Olarm Device {self.device_id}"

    @property
    def device_state(self) -> dict[str, Any] | None:
        """Return the device state."""
        return self.data.device_state if self.data else None

    @device_state.setter
    def device_state(self, value: dict[str, Any] | None) -> None:
        """Set the device state and update coordinator."""
        if self.data:
            self.data.device_state = value
            self._update_coordinator_data()

    @property
    def device_links(self) -> dict[str, Any] | None:
        """Return the device links."""
        return self.data.device_links if self.data else None

    @device_links.setter
    def device_links(self, value: dict[str, Any] | None) -> None:
        """Set the device links and update coordinator."""
        if self.data:
            self.data.device_links = value
            self._update_coordinator_data()

    @property
    def device_io(self) -> dict[str, Any] | None:
        """Return the device IO."""
        return self.data.device_io if self.data else None

    @device_io.setter
    def device_io(self, value: dict[str, Any] | None) -> None:
        """Set the device IO and update coordinator."""
        if self.data:
            self.data.device_io = value
            self._update_coordinator_data()

    @property
    def device_profile(self) -> dict[str, Any] | None:
        """Return the device profile."""
        return self.data.device_profile if self.data else None

    @property
    def device_profile_links(self) -> dict[str, Any] | None:
        """Return the device profile links."""
        return self.data.device_profile_links if self.data else None

    @property
    def device_profile_io(self) -> dict[str, Any] | None:
        """Return the device profile IO."""
        return self.data.device_profile_io if self.data else None
