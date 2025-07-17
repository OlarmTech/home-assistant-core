"""The coordinator for the olarm integration to handle API and MQTT connections."""

from __future__ import annotations

import asyncio
import logging
import ssl

from aiohttp import ClientResponseError
from olarmflowclient import OlarmFlowClient, OlarmFlowClientApiError

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class OlarmFlowClientCoordinator:
    """Manages an individual olarms config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
        olarm_client: OlarmFlowClient,
    ) -> None:
        """Create a new instance of the OlarmBroker."""

        self._hass = hass
        self._oauth_session = oauth_session

        # user props
        self._user_id = entry.data["user_id"]

        # device props
        self.device_id = entry.data["device_id"]
        self.device_name = f"Olarm Device {self.device_id}"
        self.device_state = None
        self.device_links = None
        self.device_io = None
        self.device_profile = None
        self.device_profile_links = None
        self.device_profile_io = None

        # olarm connect client
        self._olarm_connect_client = olarm_client

    async def async_setup(self) -> None:
        """Set up the coordinator; fetch device info and connect to MQTT."""
        # Fetch device information
        _LOGGER.debug("Fetching device information from Olarm API")
        await self.get_device()

    async def _ensure_valid_token(self):
        """Ensure the access token is valid and refresh if needed."""
        try:
            # Check if token needs refresh
            token_valid = self._oauth_session.valid_token
            if not token_valid:
                _LOGGER.debug("Access token expired, refreshing")
            else:
                _LOGGER.debug("Access token is still valid")

            await self._oauth_session.async_ensure_token_valid()
            new_token = self._oauth_session.token["access_token"]
            expires_at = self._oauth_session.token["expires_at"]

            # Log token info (without exposing the actual token)
            _LOGGER.debug("Access token expires at: %s ", expires_at)

            await self._olarm_connect_client.update_access_token(new_token, expires_at)
        except ClientResponseError as e:
            _LOGGER.error("Failed to refresh OAuth2 token: %s", e)

            # Check if this is an invalid_grant error (status 400) that indicates expired/invalid refresh token
            if e.status == 400:
                _LOGGER.error(
                    "OAuth2 refresh token is invalid (status 400). Integration will remain in error state"
                    "Please remove and re-add the integration to fix authentication"
                )
                raise ConfigEntryNotReady(
                    "OAuth2 refresh token is invalid. Please remove and re-add the integration."
                ) from e

            # For other HTTP errors, treat as temporary and retry
            raise ConfigEntryNotReady("Failed to refresh OAuth2 token") from e
        except Exception as e:
            _LOGGER.error("Failed to refresh OAuth2 token: %s", e)
            raise ConfigEntryNotReady("Failed to refresh OAuth2 token") from e

    async def get_device(self):
        """Retrieve device information from the Olarm API."""
        try:
            await self._ensure_valid_token()
            device = await self._olarm_connect_client.get_device(self.device_id)

            _LOGGER.debug("Device -> %s", device)

            self.device_name = (
                device.get("deviceName") or f"Olarm Device {self.device_id}"
            )
            self.device_state = device.get("deviceState")
            self.device_links = device.get("deviceLinks")
            self.device_io = device.get("deviceIO")
            self.device_profile = device.get("deviceProfile")
            self.device_profile_links = device.get("deviceProfileLinks")
            self.device_profile_io = device.get("deviceProfileIO")

            _LOGGER.debug(
                "Device -> %s",
                {
                    "device_name": self.device_name,
                    "device_state": self.device_state,
                },
            )

        except OlarmFlowClientApiError as e:
            raise ConfigEntryNotReady("Failed to reach Olarm API") from e

    async def send_device_area_cmd(self, device_id, area_status, area_index):
        """Send area command to the Olarm device."""
        try:
            await self._ensure_valid_token()
            method_name = f"send_device_area_{area_status}"
            method = getattr(self._olarm_connect_client, method_name)
            await method(device_id, area_index + 1)

        except OlarmFlowClientApiError as e:
            raise ConfigEntryNotReady("Failed to reach Olarm API") from e

    async def send_device_zone_cmd(self, device_id, zone_status, zone_index):
        """Send zone bypass or unbypass command to the Olarm device."""
        try:
            await self._ensure_valid_token()
            method_name = f"send_device_zone_{zone_status}"
            method = getattr(self._olarm_connect_client, method_name)
            await method(device_id, zone_index + 1)

        except OlarmFlowClientApiError as e:
            raise ConfigEntryNotReady("Failed to reach Olarm API") from e

    async def send_device_pgm_cmd(self, device_id, pgm_action, pgm_index):
        """Send PGM command to the Olarm device."""
        try:
            await self._ensure_valid_token()
            method_name = f"send_device_pgm_{pgm_action}"
            method = getattr(self._olarm_connect_client, method_name)
            await method(device_id, pgm_index + 1)

        except OlarmFlowClientApiError as e:
            raise ConfigEntryNotReady("Failed to reach Olarm API") from e

    async def send_device_ukey_cmd(self, device_id, ukey_index):
        """Send utility key command to the Olarm device."""
        try:
            await self._ensure_valid_token()
            await self._olarm_connect_client.send_device_ukey_activate(
                device_id, ukey_index + 1
            )

        except OlarmFlowClientApiError as e:
            raise ConfigEntryNotReady("Failed to reach Olarm API") from e

    async def send_device_link_output_cmd(
        self, device_id, link_id, output_action, output_index
    ):
        """Send link output command to the Olarm device."""
        try:
            await self._ensure_valid_token()
            method_name = f"send_device_link_output_{output_action}"
            method = getattr(self._olarm_connect_client, method_name)
            await method(device_id, link_id, output_index + 1)

        except OlarmFlowClientApiError as e:
            raise ConfigEntryNotReady("Failed to reach Olarm API") from e

    async def send_device_link_relay_cmd(
        self, device_id, link_id, output_action, output_index
    ):
        """Send link relay command to the Olarm device."""
        try:
            await self._ensure_valid_token()
            method_name = f"send_device_link_relay_{output_action}"
            method = getattr(self._olarm_connect_client, method_name)
            await method(device_id, link_id, output_index + 1)

        except OlarmFlowClientApiError as e:
            raise ConfigEntryNotReady("Failed to reach Olarm API") from e

    async def send_device_max_output_cmd(self, device_id, output_action, output_index):
        """Send max output command to the Olarm device."""
        try:
            await self._ensure_valid_token()
            method_name = f"send_device_max_output_{output_action}"
            method = getattr(self._olarm_connect_client, method_name)
            await method(device_id, output_index + 1)

        except OlarmFlowClientApiError as e:
            raise ConfigEntryNotReady("Failed to reach Olarm API") from e

    async def async_refresh_token(self):
        """Manually refresh the access token."""
        try:
            await self._ensure_valid_token()
            _LOGGER.debug("Access token refreshed successfully")
        except Exception as e:
            _LOGGER.error("Failed to refresh access token: %s", e)
            raise

    async def async_stop(self):
        """Stop and clean up MQTT and API client connections."""
        if self._olarm_connect_client:
            # stop_mqtt is synchronous, so run it in an executor
            await self._hass.async_add_executor_job(
                self._olarm_connect_client.stop_mqtt
            )
