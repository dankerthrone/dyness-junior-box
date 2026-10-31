"""Dyness Junior Box (Local) — Home-Assistant-Integration.

Lokale Steuerung & Monitoring der Dyness Junior Box über den per Reverse
Engineering entschlüsselten Dylink-Kanal (TCP 5005). Kein Cloud-Zwang.

WICHTIG für den Betrieb: Die Box verbindet sich aktiv zu logger.dyness.com.
Damit sie bei UNS anklopft, muss der DNS-Eintrag dieser Domain auf die
HA-IP umgeleitet werden (z. B. AdGuard-Home "DNS rewrite").
Siehe README.
"""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    DEFAULT_LISTEN_IP,
    DEFAULT_PORT,
    MAX_POWER_W,
    MIN_POWER_W,
    MODE_BATTERY,
    MODE_LOAD,
    MODE_SHUTDOWN,
    SERVICE_SET_DOD,
    SERVICE_SET_WORKMODE,
    CONF_LISTEN_IP,
    CONF_SERIAL,
    DOMAIN,
)
from .dylink import DylinkServer, frames

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "select", "number"]


class DynessHub:
    """Daten-Hub: hält Server + zuletzt gesehene Werte."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, server: DylinkServer) -> None:
        self.hass = hass
        self.entry = entry
        self.server = server
        self.serial = entry.data[CONF_SERIAL]
        self.firmware: str | None = None
        self.soc: int | None = None
        # Zuletzt gesetzter Sollwert (Default: sichere 150 W / Lastpriorität).
        # Die Box hat kein Read-back — das ist der eigene Merkposten.
        self.power: int = MIN_POWER_W
        self.mode: int = MODE_LOAD
        self.power_entity = None
        self.mode_entity = None

    @property
    def unique_id(self) -> str:
        return f"dyness_junior_{self.serial}"

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": f"Dyness Junior Box ({self.serial})",
            "manufacturer": "Dyness",
            "model": "Junior Box",
            "sw_version": self.firmware or "?",
        }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    serial = entry.data[CONF_SERIAL]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    listen_ip = entry.data.get(CONF_LISTEN_IP, DEFAULT_LISTEN_IP)

    server = DylinkServer(serial, host=listen_ip, port=port)
    hub = DynessHub(hass, entry, server)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub

    try:
        await server.start()
    except OSError as exc:
        _LOGGER.error("Port %s belegt oder nicht bindbar: %s", port, exc)
        raise ConfigEntryNotReady(f"Port {port} nicht bindbar") from exc

    _register_services(hass, hub)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hub = hass.data[DOMAIN].pop(entry.entry_id)
    await hub.server.stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _register_services(hass: HomeAssistant, hub: DynessHub) -> None:
    _ser = hub.serial

    async def _send(frame: bytes, label: str) -> dict:
        sent = hub.server.inject(frame)
        _LOGGER.info("%s %s: %s", label, "gesendet" if sent else "nicht gesendet (Box offline?)", frame.hex()[:48])
        return {"sent": sent, "command": label}

    async def set_workmode(call: ServiceCall) -> None:
        power = int(call.data["power"])
        mode = int(call.data.get("mode", MODE_LOAD))
        if power < MIN_POWER_W:
            _LOGGER.warning(
                "Leistung %s W abgelehnt: < %s W wird von der Box als "
                "'unbegrenzt' behandelt (Akku-Gefahr)", power, MIN_POWER_W
            )
        power = max(MIN_POWER_W, min(MAX_POWER_W, power))
        hub.power = power
        hub.mode = mode
        if hub.power_entity is not None:
            hub.power_entity.async_write_ha_state()
        if hub.mode_entity is not None:
            hub.mode_entity.async_write_ha_state()
        await _send(frames.build_workmode(_ser, mode, power), f"set_workmode(mode={mode}, power={power})")

    async def set_dod(call: ServiceCall) -> None:
        dod = int(call.data["dod"])
        await _send(frames.build_dod(_ser, max(0, min(100, dod))), f"set_dod({dod})")

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_WORKMODE,
        set_workmode,
        vol.Schema(
            {
                vol.Optional("mode", default=MODE_LOAD): vol.In(
                    (MODE_LOAD, MODE_BATTERY, MODE_SHUTDOWN)
                ),
                vol.Required("power"): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_POWER_W, max=MAX_POWER_W),
                ),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DOD,
        set_dod,
        vol.Schema(
            {
                vol.Required("dod"): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=100)
                ),
            }
        ),
    )