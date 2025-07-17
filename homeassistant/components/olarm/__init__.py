"""The olarm integration."""

from __future__ import annotations

import logging

from olarmflowclient import OlarmFlowClient, OlarmFlowClientApiError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
)
from .coordinator import OlarmFlowClientCoordinator

_PLATFORMS = [
    Platform.BINARY_SENSOR,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up olarm from a config entry."""

    # use oauth2 to get access token
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    _LOGGER.debug(
        "OAuth2 session created, access_token expires at -> %s",
        session.token["expires_at"],
    )

    # Create Olarm API client
    olarm_client = OlarmFlowClient(session.token["access_token"])

    try:
        # setup Olarm Connect coordinator
        coordinator = OlarmFlowClientCoordinator(
            hass,
            entry,
            session,
            olarm_client,
        )

        # start coordinator (fetch device and connect to MQTT)
        await coordinator.async_setup()

        # store coordinator in entry.runtime_data
        entry.runtime_data = coordinator

        _LOGGER.debug("Setting up platforms for Olarm integration")
        await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    except ConfigEntryNotReady:
        # Temporary failures (network issues, device offline, etc.) - let Home Assistant retry
        _LOGGER.debug("Olarm setup not ready, will retry later")
        raise
    except ConfigEntryError:
        # Permanent failures - setup will not be retried
        _LOGGER.error("Permanent error setting up Olarm integration")
        raise
    except OlarmFlowClientApiError as ex:
        # API errors that indicate authentication or permanent issues
        if "401" in str(ex) or "403" in str(ex) or "unauthorized" in str(ex).lower():
            _LOGGER.error("Olarm API authentication failed: %s", ex)
            raise ConfigEntryNotReady(
                "Invalid Olarm credentials. Please remove and re-add the integration."
            ) from ex
        _LOGGER.warning("Olarm API error during setup: %s", ex)
        raise ConfigEntryNotReady("Olarm API temporarily unavailable") from ex
    except (OSError, ConnectionError, TimeoutError) as ex:
        # Network-related errors that are likely temporary
        _LOGGER.warning("Network error during Olarm setup: %s", ex)
        raise ConfigEntryNotReady("Network connection to Olarm failed") from ex
    except Exception as ex:
        # Unexpected errors - log and treat as temporary to avoid permanent failure
        _LOGGER.exception("Unexpected error setting up Olarm integration")
        # Clean up any partial setup
        if hasattr(entry, "runtime_data") and entry.runtime_data:
            coordinator = entry.runtime_data
            if coordinator:
                try:
                    await coordinator.async_stop()
                except (OSError, ConnectionError, RuntimeError) as cleanup_error:
                    _LOGGER.error("Error during cleanup: %s", cleanup_error)
        raise ConfigEntryNotReady("Unexpected error during Olarm setup") from ex

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = entry.runtime_data

    # stop coordinator
    await coordinator.async_stop()

    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
