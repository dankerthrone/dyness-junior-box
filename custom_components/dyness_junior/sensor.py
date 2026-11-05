"""Sensoren der Dyness-Junior-Integration."""
from __future__ import annotations

import time

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    SENSOR_FIRMWARE,
    SENSOR_SOC,
    SENSOR_SOH,
    SENSOR_VOLTAGE,
    SENSOR_CURRENT,
    SENSOR_OUTPUT,
    MAX_POWER_W,
    MIN_POWER_W,
    DOMAIN,
)
from .dylink import parser

# Register, deren Wert je Frame-Typ erfasst wird (Frame-Typ-Erkennung für
# den Modus-Read-back: welcher Frame trägt welches Interesse-Register?).
_INTEREST_REGISTERS = {
    parser.SOC_REGISTER: "soc",
    parser.SOH_REGISTER: "soh",
    parser.VOLTAGE_REGISTER: "voltage",
    parser.CURRENT_REGISTER: "current",
    parser.LIMIT_REGISTER: "limit",
    parser.POWER_REGISTER: "power_out",
    0x1900: "0x1900",
    0x300C: "0x300c",
    0x36B0: "0x36b0",
    0x36B4: "0x36b4",
    0x3520: "0x3520",
    0x4524: "0x4524",
    0x4588: "0x4588",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub = hass.data[DOMAIN][entry.entry_id]
    fw = DynessFirmwareSensor(hub)
    soc = DynessSocSensor(hub)
    soh = DynessSohSensor(hub)
    volt = DynessVoltageSensor(hub)
    curr = DynessCurrentSensor(hub)
    outp = DynessOutputSensor(hub)
    async_add_entities([fw, soc, soh, volt, curr, outp])

    def _on_report(info: dict) -> None:
        hub.firmware = info.get("firmware")
        fw.async_write_ha_state()

    def _on_registers(ln: int, regs: dict) -> None:
        hub.registers = regs
        if regs.get(parser.SOC_REGISTER) is not None:
            hub.soc = regs[parser.SOC_REGISTER]
        if regs.get(parser.SOH_REGISTER) is not None:
            hub.soh = regs[parser.SOH_REGISTER]
        if regs.get(parser.VOLTAGE_REGISTER) is not None:
            hub.voltage = regs[parser.VOLTAGE_REGISTER]
        if regs.get(parser.CURRENT_REGISTER) is not None:
            hub.current = regs[parser.CURRENT_REGISTER]
        # Plausibilität: die Register-Semantik ist NICHT frame-typ-stabil (gemessen
        # 2026-11-01: 0x1770 lieferte 4294967127 = -169 als unsigned int32 aus einem
        # anderen Frame-Typ). Nur plausible Werte als echten Box-Zustand übernehmen;
        # Unsinn lässt den Read-back auf "zuletzt gesetzt" (hub.power) zurückfallen.
        if regs.get(parser.LIMIT_REGISTER) is not None:
            v = regs[parser.LIMIT_REGISTER]
            if MIN_POWER_W <= v <= MAX_POWER_W:
                hub.soll = v
        if regs.get(parser.POWER_REGISTER) is not None:
            v = regs[parser.POWER_REGISTER]
            if 0 <= v <= 10000:
                hub.power_out = v
        # Frame-Statistik: welcher Frame-Typ (PAYLOAD-Länge + Karten-Größe) trägt
        # welche Interesse-Register — Grundlage für Modus-Read-back. Erkenntnis
        # 2026-11-01: 0x1770 ist NICHT frame-stabil (negativer Wert = Einspeisung/
        # Ladung in einem anderen Sub-Typ mit gleicher Register-Anzahl).
        stats = hub.frame_stats.setdefault(
            f"{ln}B/{len(regs)}r",
            {"count": 0, "last": None, "regs": {}, "limit_hist": []},
        )
        stats["count"] += 1
        stats["last"] = time.strftime("%H:%M:%S")
        for key, label in _INTEREST_REGISTERS.items():
            if key in regs:
                stats["regs"][label] = regs[key]
        if parser.LIMIT_REGISTER in regs:
            stats["limit_hist"].append(regs[parser.LIMIT_REGISTER])
            stats["limit_hist"] = stats["limit_hist"][-4:]
        # Attribute (Roh-Register) auch aktualisieren, wenn keine SOC-Register dabei war
        for ent in (soc, soh, volt, curr, outp):
            ent.async_write_ha_state()

    hub.server.on_report = _on_report
    hub.server.on_registers = _on_registers


class DynessSensorBase(SensorEntity):
    _attr_should_poll = False

    def __init__(self, hub) -> None:
        self._hub = hub
        self._attr_device_info = hub.device_info

    @property
    def available(self) -> bool:
        return True


class DynessFirmwareSensor(DynessSensorBase):
    _attr_icon = "mdi:chip"
    _attr_name = SENSOR_FIRMWARE

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self._attr_unique_id = f"{hub.unique_id}_firmware"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str | None:
        return self._hub.firmware


class DynessSocSensor(DynessSensorBase):
    """SOC — Register 0x0320, validated against Cloud-API + Tasmota."""

    _attr_icon = "mdi:battery"
    _attr_name = SENSOR_SOC
    _attr_native_unit_of_measurement = "%"
    _attr_device_class = SensorDeviceClass.BATTERY

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self._attr_unique_id = f"{hub.unique_id}_soc"

    @property
    def native_value(self) -> int | None:
        return self._hub.soc

    @property
    def extra_state_attributes(self) -> dict:
        """Roh-Register als Hex-Karte — für die laufende Kalibrierung."""
        regs = self._hub.registers or {}
        return {
            "register": {hex(k): v for k, v in sorted(regs.items())},
            "frame_stats": self._hub.frame_stats,
        }


class DynessSohSensor(DynessSensorBase):
    """SOH (Batterie-Gesundheit) — Register 0x04B0, gegen Cloud-SOH gecheckt."""

    _attr_icon = "mdi:battery-heart"
    _attr_name = SENSOR_SOH
    _attr_native_unit_of_measurement = "%"
    _attr_device_class = SensorDeviceClass.BATTERY

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self._attr_unique_id = f"{hub.unique_id}_soh"

    @property
    def native_value(self) -> int | None:
        return self._hub.soh


class DynessVoltageSensor(DynessSensorBase):
    """Battery voltage — Register 0x0258 (Float), checked against Cloud-API."""

    _attr_icon = "mdi:sine-wave"
    _attr_name = SENSOR_VOLTAGE
    _attr_native_unit_of_measurement = "V"
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_suggested_display_precision = 2

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self._attr_unique_id = f"{hub.unique_id}_voltage"

    @property
    def native_value(self) -> float | None:
        return self._hub.voltage


class DynessCurrentSensor(DynessSensorBase):
    """Batteriestrom — Register 0x02BC (Float), negativ = Entladen."""

    _attr_icon = "mdi:current-dc"
    _attr_name = SENSOR_CURRENT
    _attr_native_unit_of_measurement = "A"
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_suggested_display_precision = 2

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self._attr_unique_id = f"{hub.unique_id}_current"

    @property
    def native_value(self) -> float | None:
        return self._hub.current


class DynessOutputSensor(DynessSensorBase):
    """Ausgangsleistung AC der Box — Register 0x17D4 (matcht Tasmota)."""

    _attr_icon = "mdi:meter-electric-outline"
    _attr_name = SENSOR_OUTPUT
    _attr_native_unit_of_measurement = "W"
    _attr_device_class = SensorDeviceClass.POWER

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self._attr_unique_id = f"{hub.unique_id}_output"

    @property
    def native_value(self) -> int | None:
        return self._hub.power_out