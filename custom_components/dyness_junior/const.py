"""Konstanten der Dyness-Junior-Integration."""
from __future__ import annotations

DOMAIN = "dyness_junior"

CONF_SERIAL = "serial"
CONF_PORT = "port"
CONF_LISTEN_IP = "listen_ip"

DEFAULT_PORT = 5005
DEFAULT_LISTEN_IP = "0.0.0.0"

# Dylink-Protokoll
DLINK_BANNER = (
    b"\x00\x00\x7fThis is dyness.raymon service. node id is "
    b"'00a9f0a9-7176-41b7-a1c5-0a5873849339'"
)

# Service-Namen (HA-Services)
SERVICE_SET_WORKMODE = "set_workmode"
SERVICE_SET_DOD = "set_dod"

# Sicherheits-Grenzen (siehe docs/ROADMAP.md):
# Die Box verwirft Leistungen < 150 W als "unbegrenzt" — das kann den Akku
# bis zum BMS-Schutz entladen. Niemals quiet unter 150 W gehen.
MIN_POWER_W = 150
MAX_POWER_W = 800

# Mode-Werte laut SetWorkModeSetting: 16 = Lastpriorität, 17 = Batteriepriorität,
# 255 = Shutdown.
MODE_LOAD = 16
MODE_BATTERY = 17
MODE_SHUTDOWN = 255

# Sensornamen (v1.1.0: "(experimentell)" entfernt — Register 0x0320/0x04B0/0x0258/0x02BC
# sind seit 2026-10-31 mehrfach gegen Cloud-API + Tasmota validiert)
SENSOR_CONNECTION = "Verbindung"
SENSOR_FIRMWARE = "Firmware"
SENSOR_SOC = "SOC"
SENSOR_SOH = "SOH"
SENSOR_VOLTAGE = "Spannung"
SENSOR_CURRENT = "Strom"
SENSOR_OUTPUT = "Ausgangsleistung"