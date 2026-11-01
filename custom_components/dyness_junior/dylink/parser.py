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


_TAG_INT32 = (0x49, 0x4C)   # int32 BE (4 Bytes) — z. B. 0x17D4 (Ausgang), 0x238C (Kapazität)
_TAG_INT16 = (0x53,)        # int16 BE, ab Wertbeginn (Bytes 1-2) — z. B. 0x0320 (SOC)
_TAG_FLOAT = (0x46,)        # float32 BE — z. B. 0x025C (Volt), 0x02BC (Ampere)


def parse_registers(payload: bytes) -> dict[int, int | float]:
    """Register-Raster [key16][tag][4B-Wert] → {key: wert}.

    Formate gemessen (2026-10-31, Relay-Mitschnitt gegen echte Cloud):
    Tag 0x49/0x4C = int32 BE, Tag 0x53 = int16 BE ab Wertbeginn,
    Tag 0x46 = float32 BE. Achtung: die alte Lesart (alle Tags als int16 ab
    Wertbeginn) verlas Werte im 0x49-Raster (0x1900=16 wurde als 0 gelesen).
    """
    import struct
    regs: dict[int, int | float] = {}
    i = 0
    n = len(payload)
    while i + 4 < n:
        key = int.from_bytes(payload[i:i + 2], "big")
        tag = payload[i + 2]
        if i + 7 <= n and tag in _TAG_INT32:
            regs[key] = int.from_bytes(payload[i + 3:i + 7], "big")
            i += 7
        elif i + 7 <= n and tag in _TAG_FLOAT:
            regs[key] = round(struct.unpack(">f", payload[i + 3:i + 7])[0], 3)
            i += 7
        elif i + 5 <= n and tag in _TAG_INT16:
            regs[key] = int.from_bytes(payload[i + 3:i + 5], "big")
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
# Gemessen am 2026-10-31 (Relay-Mitschnitt, Differenztest 250→200→150 W):
VOLTAGE_REGISTER = 0x0258    # tag 0x46, V (16,2-16,4 V, gemessen)
CURRENT_REGISTER = 0x02BC    # tag 0x46, A, negativ = Entladen (ca. -9 A)
LIMIT_REGISTER = 0x1770      # tag 0x49 — KEIN Sollwert-Read-back! Gemessen 2026-11-01:
                             # Bilanz-/Netto-Leistung, schwankt -244…+18 W bei festem Soll
                             # 150/200 W (Wert folgt Writes NICHT). Nur Plausibilitäts-
                             # Konstante: echte 150-800-W-Sollwerte (falls je ein Frame
                             # sie traegt) sollen durch den Filter (sensor.py) dürfen.
POWER_REGISTER = 0x17D4      # tag 0x49, Ausgangsleistung AC W (matcht Tasmota)
CAPACITY_REGISTER = 0x238C   # tag 0x49, Nennkapazität Wh (2000)