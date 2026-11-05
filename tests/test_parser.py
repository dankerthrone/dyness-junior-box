"""Parser tests. Regression: the register grid is [key32][tag][Wert], NOT
[key16][tag][4B] as the old parser wrongly assumed (constant 2-byte drift →
fake values like 0x17D4=281 W, and the 115r/116r raster shift).

Fixtures use REAL bytes from the 1082B telemetry frames captured via the MM
relay (~/dyness-probe/relay_5005_full.log): 0x0320=12 % SOC, 0x04B0=100 SOH,
0x02BC≈4.1 A.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import dylink.parser as parser

# Echo der echten 1082B-Telemetrie (führender Registerblock):
#   0x02BC(46, float 4.1) | 0x0320(53, 12) | 0x04B0(53, 100)
_REAL_GRID = bytes.fromhex("000002bc46408333330000032053000c000004b0530064")


def test_float_record_advances_9_and_key_is_4_bytes():
    # 00 00 02 bc | 46 | 40 83 33 33 == key4=0x02bc, tag float, val 4.1
    regs = parser.parse_registers(_REAL_GRID)
    assert abs(regs[0x02BC] - 4.1) < 1e-3


def test_int16_registers_soc_soh():
    regs = parser.parse_registers(_REAL_GRID)
    assert regs[0x0320] == 12      # SOC %
    assert regs[0x04B0] == 100     # SOH %


def test_known_constants_unchanged_numerically():
    # Der 4-Byte-Key 00 00 03 20 == numerisch 0x0320 -> vorhandene Konstanten
    # gelten unverändert (sensor.py / hub bleiben kompatibel).
    assert parser.SOC_REGISTER == 0x0320
    assert parser.SOH_REGISTER == 0x04B0
    assert parser.VOLTAGE_REGISTER == 0x0258
    assert parser.CURRENT_REGISTER == 0x02BC
    assert parser.POWER_REGISTER == 0x17D4


def test_capacity_int32():
    # 0x238C int32 2000 (Nennkapazität Wh)
    regs = parser.parse_registers(bytes.fromhex("0000238c49000007d0"))
    assert regs[0x238C] == 2000


def test_unknown_tag_does_not_byte_drift():
    # Zwischen zwei gültigen Records ein unbekannter Block: der Parser darf
    # nicht um 1 Byte verrutschen, sonst wäre 0x04B0 nicht mehr erreichbar.
    payload = (
        bytes.fromhex("0000032053000c")   # SOC 12
        + bytes.fromhex("deadbeef")       # nicht-registrischer Zwischenblock
        + bytes.fromhex("000004b0530064") # SOH 100
    )
    regs = parser.parse_registers(payload)
    assert regs.get(0x0320) == 12
    assert regs.get(0x04B0) == 100


def test_no_exception_on_truncated_tail():
    # Abgeschnittene Tail-Bytes dürfen nicht crashen
    assert parser.parse_registers(bytes.fromhex("000002")) == {}
    assert parser.parse_registers(b"") == {}


def test_register_count_stable_across_real_frames():
    """Regression 115r/116r: gleiche Frame-Länge → gleiche Register-Anzahl.

    .log-Dateien sind per *.log-Regel gitignored → skip, wenn nicht vorhanden.
    """
    log = Path.home() / "dyness-probe/relay_5005_full.log"
    if not log.exists():
        pytest.skip("relay-Mitschnitt nicht vorhanden (gitignored)")
    text = log.read_text(encoding="utf-8", errors="replace")
    pat = re.compile(r"\[(\d\d:\d\d:\d\d)\]\s*[<>]\s*(\d+)B:\s*([0-9a-fA-F ]+)")
    sizes = {}            # len(regs) -> Anzahl Samples (muss stabil sein)
    socs = set()
    for _, _, h in pat.findall(text):
        raw = bytes.fromhex(h.replace(" ", ""))
        if len(raw) < 8:
            continue
        ln = int.from_bytes(raw[:4], "big")
        if ln != 1082:
            continue
        regs = parser.parse_registers(raw[4:4 + ln])
        sizes[len(regs)] = sizes.get(len(regs), 0) + 1
        if 0x0320 in regs:
            socs.add(regs[0x0320])
    assert len(sizes) == 1, f"Raster-Rutsch: ungleiche Register-Anzahlen {sizes}"
    assert socs, "kein SOC-Register (0x0320) aus den echten Frames geparst"