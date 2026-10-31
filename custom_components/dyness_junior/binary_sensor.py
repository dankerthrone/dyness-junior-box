"""Binärsensor: Verbindungsstatus der Box zum lokalen Dylink-Server."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SENSOR_CONNECTION


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub = hass.data[DOMAIN][entry.entry_id]
    conn = DynessConnectionSensor(hub)
    async_add_entities([conn])

    def _on_state(state: dict) -> None:
        conn.async_write_ha_state()

    hub.server.on_state = _on_state


class DynessConnectionSensor(BinarySensorEntity):
    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = SENSOR_CONNECTION
    _attr_icon = "mdi:lan-connect"

    def __init__(self, hub) -> None:
        self._hub = hub
        self._attr_unique_id = f"{hub.unique_id}_connection"
        self._attr_device_info = hub.device_info

    @property
    def is_on(self) -> bool:
        return self._hub.server.connected