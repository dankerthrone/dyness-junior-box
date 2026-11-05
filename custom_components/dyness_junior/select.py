"""Modus (Select-Entity) der Dyness-Junior-Integration.

Dropdown/Drei-Buttons: Lastpriorität / Batteriepriorität / Aus (Shutdown).
Jede Änderung schickt einen SetWorkModeSetting-Frame (00 78) mit der
zuletzt gesetzten Leistungsgrenze an die Box.

Read-back (2026-11-05): Der Zeitplan-Modus ist über das beobachtete Protokoll
nicht lesbar. LESBAR ist allein der BASIS-Modus (Register 0x1900, die Ebene,
die die App via SetBaseSetting schreibt). current_option zeigt den ECHTEN
Basis-Modus, wenn er aus der Telemetrie vorliegt; sonst den ZULETZT GESETZTEN
Schedule-Wert. Der Schedule-Sollwert liegt zusätzlich als Attribut
`zeitplan_sollwert` / `zeitplan_code` vor — die Ebenen werden bewusst getrennt.
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

# DOD im Shutdown-Frame: der zuletzt per Service gesetzte User-Wert (95 %).
_SHUTDOWN_DOD_PCT = 95

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
        # Echter Read-back, wenn möglich: der Basis-Modus (0x1900) ist der
        # einzig real lesbare Modus-Zustand. Ohne 0x1900 (noch nicht gelesen)
        # Fallback auf den zuletzt per Schedule gesetzten Wert.
        if self._hub.base_mode is not None and self._hub.base_mode in MODE_OPTIONS:
            return MODE_OPTIONS[self._hub.base_mode]
        return MODE_OPTIONS.get(self._hub.mode)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "box_bestaetigung": self._hub.command_confirmed_at or "noch keine",
            # Echter Basis-Modus (0x1900, SetBase-Ebene): der einzige lesbare.
            "basis_modus_lesbar": self._hub.base_mode is not None,
            "basis_modus": self._hub.base_mode,
            "basis_modus_zeit": self._hub.base_mode_at or "keine",
            # Schedule (SetWorkModeSetting) — das, was unser Select/Service setzt;
            # ist über das Protokoll NICHT lesbar, daher nur "zuletzt gesetzt".
            "zeitplan_sollwert": MODE_OPTIONS.get(self._hub.mode),
            "zeitplan_code": self._hub.mode,
        }

    async def async_select_option(self, option: str) -> None:
        mode = {v: k for k, v in MODE_OPTIONS.items()}[option]
        if mode == MODE_SHUTDOWN and len(self._hub.serial) != 16:
            # Shutdown frame template is 16-byte-serial-bound; never fake an
            # "off" state we couldn't send. Keep current selection unchanged.
            _LOGGER.error(
                "Shutdown requires a 16-character serial (got %s); selecting "
                "'%s' ignored, no frame sent.", len(self._hub.serial), option
            )
            return
        self._hub.mode = mode
        if mode == MODE_SHUTDOWN:
            # Echter Shutdown: SetBaseSetting-Frame (0x1900=ff), wie die App ihn
            # sendet — SetWorkMode-255 ist wirkungslos (bewiesen 2026-11-02).
            frame = frames.build_shutdown(
                self._hub.serial, self._hub.power, _SHUTDOWN_DOD_PCT
            )
        else:
            frame = frames.build_workmode(self._hub.serial, mode, self._hub.power)
        sent = self._hub.server.inject(frame)
        _LOGGER.info(
            "Modus %s (Leistungsgrenze %s W): %s",
            option,
            self._hub.power,
            "gesendet" if sent else "nicht gesendet (Box offline?)",
        )