"""Best-effort-Dekodierung der Telemetrie-/Konfig-Frames der Box.

Hinweis (ehrlich): Register-Semantik (welche Adresse = SOC, Spannung, Strom)
ist noch nicht gegen Ground-Truth validiert — die SOC-Heuristik ist EXPERIMENTELL
und wird in v0.2 mit Live-Referenz (Cloud-API + Tasmota) verifiziert.
"""
from __future__ import annotations

import re


def parse_config_report(payload: bytes) -> dict:
    """Aus dem ~475B-Konfigbericht die Klartext-Felder ziehen (MAC, FW, Hosts...)."""
    info: dict = {}
    if b"RSW_" in payload:
        m = re.search(rb"RSW_[\w.\-]+", payload)
        if m:
            info["firmware"] = m.group(0).decode()
    if b"90EB" in payload or re.search(rb"[0-9A-F]{12}", payload):
        m = re.search(rb"(?<![0-9A-F])([0-9A-F]{12})(?![0-9A-F])", payload)
        if m:
            info["mac"] = m.group(1).decode()
    hosts = re.findall(rb"([a-z0-9.\-]+\.(?:dyness\.com|raymoniot\.com))", payload)
    if hosts:
        info["hosts"] = sorted({h.decode() for h in hosts})
    if b"DHCP," in payload:
        m = re.search(rb"DHCP,([0-9.,]+)", payload)
        if m:
            info["dhcp"] = m.group(1).decode()
    m = re.search(rb"http://([0-9a-z.\-]+):(\d+)/[a-z\-]+", payload)
    if m:
        info["api_url"] = f"http://{m.group(1).decode()}:{m.group(2).decode()}"
    return info


_REGISTER_TAGS = (0x49, 0x53)  # int-tags im Datenraster


def parse_registers(payload: bytes) -> dict[int, int]:
    """Register-Raster [key16][tag][4B-Wert] → {key: wert16-be}.

    Wert-Heuristik: 16-Bit-Big-Endian ab Wertbeginn (Belege: 0x4524 = 0x000e = 14,
    0x04b0 = 0x0064 = 100). Experimentell — Semantik wird in v0.2 mit
    Ground-Truth (Cloud-API + Tasmota) verifiziert.
    """
    regs: dict[int, int] = {}
    i = 0
    n = len(payload)
    while i + 4 < n:
        key = int.from_bytes(payload[i:i + 2], "big")
        tag = payload[i + 2]
        if tag in _REGISTER_TAGS:
            val = int.from_bytes(payload[i + 3:i + 5], "big")
            regs[key] = val
            i += 7
        else:
            i += 1
    return regs


# Register-Heuristik (Kalibrierung 2026-10-31 LIVE bestätigt via Relay zur echten
# Cloud, 688-B-Telemetrie-Frame): 0x0320 = SOC (%) — Wert 72 nach ~2,5 h Entladung
# aus vollem Akku (vorher 12→13 bei ~13 % SOC am Morgen). 0x04B0 = SOH (%)
# konstant 100 (= Cloud-SOH; war fälschlich als SOC angenommen — bei leerem Akku
# stand dort weiter 100).
SOC_REGISTER = 0x0320
SOH_REGISTER = 0x04B0