"""Sensoren der Dyness-Junior-Integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SENSOR_FIRMWARE, SENSOR_SOC, DOMAIN
from .dylink import parser


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub = hass.data[DOMAIN][entry.entry_id]
    fw = DynessFirmwareSensor(hub)
    soc = DynessSocSensor(hub)
    async_add_entities([fw, soc])

    def _on_report(info: dict) -> None:
        hub.firmware = info.get("firmware")
        fw.async_write_ha_state()

    def _on_registers(regs: dict) -> None:
        soc_value = regs.get(parser.SOC_REGISTER)
        if soc_value is not None:
            hub.soc = soc_value
            soc.async_write_ha_state()

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
    """SOC — experimentell (Register-Heuristik; Ground-Truth-Check in v0.2)."""

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
        return {"hinweis": "experimentell — Verifikation gegen Live-Referenz in v0.2"}