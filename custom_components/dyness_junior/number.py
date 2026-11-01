"""Leistungsgrenze (Number-Entity) der Dyness-Junior-Integration.

Schieberegler 150-800 W; jede Wertänderung schickt sofort einen
SetWorkModeSetting-Frame (00 78) mit dem zuletzt gewählten Modus an die Box.
"""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAX_POWER_W, MIN_POWER_W
from .dylink import frames

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub = hass.data[DOMAIN][entry.entry_id]
    ent = DynessPowerLimitNumber(hub)
    hub.power_entity = ent
    async_add_entities([ent])


class DynessPowerLimitNumber(NumberEntity):
    """Leistungsgrenze der Box (Sollwert der Gesamt-Ausgangsleistung)."""

    _attr_should_poll = False
    _attr_icon = "mdi:gauge"
    _attr_name = "Leistungsgrenze"
    _attr_native_min_value = MIN_POWER_W
    _attr_native_max_value = MAX_POWER_W
    _attr_native_step = 10
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_mode = NumberMode.AUTO

    def __init__(self, hub) -> None:
        self._hub = hub
        self._attr_device_info = hub.device_info
        self._attr_unique_id = f"{hub.unique_id}_power_limit"

    @property
    def native_value(self) -> float | None:
        # Read-back: 0x1770 ist KEIN stabiler Sollwert (gemessen 2026-11-01:
        # Bilanz-/Netto-Leistung, schwankt negativ bis positiv, unabhängig vom
        # Soll). Der Plausibilitäts-Filter (150-800 W) lässt echte Sollwerte
        # durch; sonst "zuletzt gesetzter Wert" (bestätigt via 91-78-ACK).
        if self._hub.soll is not None:
            return float(self._hub.soll)
        return float(self._hub.power)

    @property
    def extra_state_attributes(self) -> dict:
        return {"box_bestaetigung": self._hub.command_confirmed_at or "noch keine"}

    async def async_set_native_value(self, value: float) -> None:
        power = int(value)
        self._hub.power = power
        sent = self._hub.server.inject(
            frames.build_workmode(self._hub.serial, self._hub.mode, power)
        )
        _LOGGER.info(
            "Leistungsgrenze %s W (mode %s): %s",
            power,
            self._hub.mode,
            "gesendet" if sent else "nicht gesendet (Box offline?)",
        )