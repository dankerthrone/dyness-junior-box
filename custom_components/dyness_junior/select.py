"""Modus (Select-Entity) der Dyness-Junior-Integration.

Dropdown/Drei-Buttons: Lastpriorität / Batteriepriorität / Aus (Shutdown).
Jede Änderung schickt einen SetWorkModeSetting-Frame (00 78) mit der
zuletzt gesetzten Leistungsgrenze an die Box.

Achtung: Die Box hat kein Read-back — die Entität zeigt den ZULETZT
GESETZTEN Modus, nicht den tatsächlich aktiven der Box.
"""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODE_BATTERY, MODE_LOAD, MODE_SHUTDOWN
from .dylink import frames

_LOGGER = logging.getLogger(__name__)

MODE_OPTIONS = {
    MODE_LOAD: "Lastpriorität",
    MODE_BATTERY: "Batteriepriorität",
    MODE_SHUTDOWN: "Aus (Shutdown)",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub = hass.data[DOMAIN][entry.entry_id]
    ent = DynessModeSelect(hub)
    hub.mode_entity = ent
    async_add_entities([ent])


class DynessModeSelect(SelectEntity):
    """Betriebsmodus der Box."""

    _attr_should_poll = False
    _attr_icon = "mdi:power-plug"
    _attr_name = "Modus"
    _attr_options = list(MODE_OPTIONS.values())

    def __init__(self, hub) -> None:
        self._hub = hub
        self._attr_device_info = hub.device_info
        self._attr_unique_id = f"{hub.unique_id}_mode"

    @property
    def current_option(self) -> str | None:
        return MODE_OPTIONS.get(self._hub.mode)

    @property
    def extra_state_attributes(self) -> dict:
        return {"box_bestaetigung": self._hub.command_confirmed_at or "noch keine"}

    async def async_select_option(self, option: str) -> None:
        mode = {v: k for k, v in MODE_OPTIONS.items()}[option]
        self._hub.mode = mode
        sent = self._hub.server.inject(
            frames.build_workmode(self._hub.serial, mode, self._hub.power)
        )
        _LOGGER.info(
            "Modus %s (Leistungsgrenze %s W): %s",
            option,
            self._hub.power,
            "gesendet" if sent else "nicht gesendet (Box offline?)",
        )