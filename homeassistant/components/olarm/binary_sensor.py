"""Support for Olarm binary sensors."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add binary sensors for a config entry."""

    _LOGGER.debug("config_entry -> %s", config_entry.data)

    # get coordinator
    coordinator = config_entry.runtime_data.coordinators[config_entry.data["device_id"]]

    # cycle through zones and create binary sensors
    sensors: list[OlarmBinarySensor] = []
    if coordinator.device_profile is not None and coordinator.device_state is not None:
        for zone_index, zone_state in enumerate(coordinator.device_state.get("zones")):
            sensors.append(
                OlarmBinarySensor(
                    coordinator,
                    "zone",
                    config_entry.data["device_id"],
                    zone_index,
                    zone_state,
                    coordinator.device_profile.get("zonesLabels")[zone_index],
                    coordinator.device_profile.get("zonesTypes")[zone_index],
                )
            )
            # load bypass entities if enabled
            if config_entry.data.get("load_zones_bypass_entities"):
                sensors.append(
                    OlarmBinarySensor(
                        coordinator,
                        "zone_bypass",
                        config_entry.data["device_id"],
                        zone_index,
                        zone_state,
                        coordinator.device_profile.get("zonesLabels")[zone_index],
                        coordinator.device_profile.get("zonesTypes")[zone_index],
                    )
                )

    # setup binary sensor for AC power
    if coordinator.device_state is not None:
        ac_power_state = "off"
        if coordinator.device_state.get("powerAC") == "ok":
            ac_power_state = "on"
        if coordinator.device_state.get("power", {}).get("AC") == "1":
            ac_power_state = "on"
        sensors.append(
            OlarmBinarySensor(
                coordinator,
                "ac_power",
                config_entry.data["device_id"],
                0,
                ac_power_state,
                "AC Power",
                None,
            )
        )

    async_add_entities(sensors)


class OlarmBinarySensor(BinarySensorEntity):
    """Define a SmartThings Binary Sensor."""

    def __init__(
        self,
        coordinator,
        sensor_type,
        device_id,
        sensor_index,
        sensor_state,
        sensor_label,
        sensor_class=None,
        link_id=None,
        link_name: str | None = "",
    ) -> None:
        """Init the class."""

        # set attributes
        self._attr_has_entity_name = True
        self._attr_name = f"Zone {sensor_index + 1:03} - {sensor_label}"
        self._attr_unique_id = f"{device_id}.zone.{sensor_index}"
        if sensor_type == "zone_bypass":
            self._attr_name = f"Zone {sensor_index + 1:03} Bypass - {sensor_label}"
            self._attr_unique_id = f"{device_id}.zone.bypass.{sensor_index}"
        if sensor_type == "ac_power":
            self._attr_name = f"{sensor_label}"
            self._attr_unique_id = f"{device_id}.ac_power"

        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=coordinator.device_name,
            manufacturer="Olarm",
        )

        _LOGGER.debug(
            "BinarySensor: init %s -> %s -> %s",
            sensor_type,
            self._attr_name,
            sensor_state,
        )

        # set the class attribute if zone type is set
        if sensor_class == 10:
            self._attr_device_class = BinarySensorDeviceClass.DOOR
        elif sensor_class == 11:
            self._attr_device_class = BinarySensorDeviceClass.WINDOW
        elif sensor_class in (20, 21):
            self._attr_device_class = BinarySensorDeviceClass.MOTION

        # custom attributes
        self.sensor_type = sensor_type
        self.device_id = device_id
        self.sensor_index = sensor_index
        self.sensor_state = sensor_state
        self.sensor_label = sensor_label
        self.sensor_class = sensor_class
        self.link_id = (
            link_id  # only used for olarm LINKs to track which LINK as can have upto 8
        )
        self._unsubscribe_dispatcher: Callable[[], None] | None = None

        # set state if zone is active[a] or closed[c] or bypassed[b]
        if (
            (self.sensor_type == "zone" and self.sensor_state == "a")
            or (self.sensor_type == "zone_bypass" and self.sensor_state == "b")
            or (self.sensor_type == "ac_power" and self.sensor_state == "on")
        ):
            self._attr_is_on = True
        else:
            self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Register the signal listener when the entity is added."""
        await super().async_added_to_hass()
        self._unsubscribe_dispatcher = async_dispatcher_connect(
            self.hass, "olarm_mqtt_update", self._handle_mqtt_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from dispatcher when entity is removed."""
        if self._unsubscribe_dispatcher:
            self._unsubscribe_dispatcher()
        await super().async_will_remove_from_hass()

    def _handle_mqtt_update(self, device_id, device_state, device_links, device_io):
        """Handle state updates from MQTT messages."""

        # check if the device_id is the same as the device_id
        if device_id != self.device_id:
            return

        # update state
        if (self.sensor_type in {"zone", "zone_bypass"}) and device_state is not None:
            self.sensor_state = device_state.get("zones")[self.sensor_index]
        elif self.sensor_type == "ac_power" and device_state is not None:
            ac_power_state = "off"
            if device_state.get("powerAC") == "ok":
                ac_power_state = "on"
            if device_state.get("power", {}).get("AC") == "1":
                ac_power_state = "on"
            self.sensor_state = ac_power_state

        # set state if zone is active[a] or closed[c] or bypassed[b]
        if (
            (self.sensor_type == "zone" and self.sensor_state == "a")
            or (self.sensor_type == "zone_bypass" and self.sensor_state == "b")
            or (self.sensor_type == "ac_power" and self.sensor_state == "on")
        ):
            self._attr_is_on = True
        else:
            self._attr_is_on = False

        self.schedule_update_ha_state()

    @property
    def name(self) -> str | None:
        """The name of the zone from the Alarm Panel."""
        return self._attr_name

    @property
    def is_on(self) -> bool | None:
        """Whether the sensor/zone is active or not."""
        return self._attr_is_on
