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


# Register-Grid (messgeprüft 2026-11-05, tools/analyze_frame_geometry.py, gegen
# die 1082B-Telemetrie-Frames verifiziert): JEDER Record ist
#   [key: 4 Bytes BE][tag: 1 Byte][Wert: tag-abhängig]
# DIE FRÜHERE ANNAHME "[key16][tag][4B]" WAR FALSCH: der Parser las den Key nur
# 2 Bytes und driftete dadurch konstant (Falschwerte, z. B. 0x17D4 281 statt
# 167 W; 115r/116r-Raster-Rutsch). Mit key4 + tag-abhängiger Breite parst
# 0x02BC(float, 16.26 V / Strom), 0x0320(53, int16: 12=12 %), 0x04B0(53, 100),
# 0x17D4(49, int32) korrekt und frame-typ-stabil.
# Wertbreiten: 0x53 = int16 (2 B), 0x46 = float32 (4 B), 0x49/0x4C = int32 (4 B).
_TAG_INT32 = (0x49, 0x4C)
_TAG_INT16 = (0x53,)
_TAG_FLOAT = (0x46,)
_VALUE_WIDTH = {0x53: 2, 0x46: 4, 0x49: 4, 0x4C: 4}
_KEY_LEN = 4
# Wie weit der Grid-Start per Scan gesucht wird (Header-Länge variiert je
# Frame-Typ: 475B=+~55, 1082B=+67, 1088B=+69 — gemessen 2026-11-05).
_GRID_SCAN = 72
# Register, deren Treffer den Grid-Scan absichern (müssen gefunden werden).
_KNOWN_FOR_SCORE = {
    0x0320, 0x04B0, 0x0258, 0x02BC, 0x17D4, 0x1770, 0x1900, 0x238C,
    0x1AF4, 0x1B58,
}


def _walk_registers(payload: bytes, start: int) -> tuple[dict[int, int | float], int]:
    """7-Byte-Grid ab `start`: [key32][tag][Wert]. Gibt (regs, unknown) zurück.

    Bei unbekanntem Tag NICHT `i += 1` (erzeugte Byte-Drift/115r-116r),
    sondern den Key überspringen, damit die Grid-Ausrichtung erhalten bleibt.
    """
    import struct
    regs: dict[int, int | float] = {}
    unknown = 0
    i = start
    n = len(payload)
    while i + _KEY_LEN + 1 < n:
        key = int.from_bytes(payload[i:i + _KEY_LEN], "big")
        tag = payload[i + _KEY_LEN]
        w = _VALUE_WIDTH.get(tag)
        if w is None:
            unknown += 1
            i += _KEY_LEN  # Re-Sync zur nächsten Key-Grenze
            continue
        end = i + _KEY_LEN + 1 + w
        if end > n:
            break
        if tag in _TAG_FLOAT:
            regs[key] = round(struct.unpack(">f", payload[i + _KEY_LEN + 1:end])[0], 3)
        else:
            regs[key] = int.from_bytes(payload[i + _KEY_LEN + 1:end], "big")
        i = end
    return regs, unknown


def parse_registers(payload: bytes) -> dict[int, int | float]:
    """Register-Raster [key32][tag][Wert] → {key: wert} (key = 4 Bytes BE).

    Der Frame-Header (0x10 + 16B S/N + cmd/Seq, je Länge verschieden) wird
    NICHT als Register gelesen. Da die Header-Länge nicht fest ist, wird der
    Grid-Start automatisch per Scan (0..GRID_SCAN) gewählt: der Offset mit den
    meisten Records bei möglichst wenigen unbekannten Tags und möglichst
    vielen Treffern auf bekannte Register. Das eliminiert den früheren
    2-Byte-Schlüssel-Fehler UND den 115r/116r-Raster-Rutsch.
    """
    best = None  # (score, regs)
    for start in range(_GRID_SCAN):
        regs, unknown = _walk_registers(payload, start)
        if not regs:
            continue
        hit = sum(1 for k in regs if k in _KNOWN_FOR_SCORE)
        score = len(regs) - 5 * unknown + 40 * hit
        if best is None or score > best[0]:
            best = (score, regs)
    return best[1] if best else {}


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
# Temperatur-Kandidaten (experimentell, Werte-Skalierung offen -> Live-Kalibrierung):
TEMP1_REGISTER = 0x1AF4      # steigt bei Entladung (beobachtet); Einheit/Skalierung offen
TEMP2_REGISTER = 0x1B58