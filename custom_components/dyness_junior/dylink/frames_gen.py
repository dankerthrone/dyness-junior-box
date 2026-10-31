"""Generierte Dylink-Templates — REST nach dem <SN>-Feld, damit die S/N
aus der HA-Konfig kommt. Regenerator: tools/gen_frames.py.
Stand: 2026-10-31 (WorkMode-Frame von der Box nachweislich mit 91-78 quittiert).
"""
from __future__ import annotations

WM_REST = bytes.fromhex("007836b200021052303745383534363638314130313231014a0ca97cb7a8700000000007000020d0491013000000001fa4497fff0000000021344902000000000022c449020000000000245449020000000000200849000000000000206c493709000000000000")
# Offset des Paars <mode> <power/8> innerhalb WM_REST
WM_MODE_POWER_OFF = 41

SB_REST = bytes.fromhex("007836b200021052303745383534363638314130313231014a0ca97cb7a8700000000001000019c8495000000000000000")
# Offset des DOD-Bytes innerhalb SB_REST (dezimal: 80->0x50, 95->0x5f)
SB_DOD_OFF = 41

BANNER = b"\x00\x00\x7fThis is dyness.raymon service. node id is '00a9f0a9-7176-41b7-a1c5-0a5873849339'"

def build(serial: bytes, rest: bytes) -> bytes:
    """Frame: 4B-Praefix = Laenge des kompletten Body (0x10 + SN + rest)."""
    body = b"\x10" + serial + rest
    return len(body).to_bytes(4, "big") + body

def login_ack(serial: bytes) -> bytes:
    return build(serial, b"\x91\x00\x01")

def ack_telem(serial: bytes) -> bytes:
    return build(serial, b"\x99\x04\x01")

def ack_cfgrep(serial: bytes) -> bytes:
    return build(serial, b"\x99\x71\x01")

def bind_ack(serial: bytes, token: bytes) -> bytes:
    # 0xa1 0x93 wie der echte Server (nicht 0xa1 0x91) — gemessen 2026-10-31
    return build(serial, b"\x91\x22\x00\x00\x01\xa1\x93" + token)

def time_push(serial: bytes) -> bytes:
    """Zeitsync im echten Server-Format (gemessen 2026-10-31 per Relay).

    Format: 00 77 00 00 12 f8 13 a0 0a 01 08 02 00 08 <sek> <min> 15 1f 0a 1a 06 01 <rand2> d0 0d
    <sek> = aktuelle Sekunde, <min> = aktuelle Minute (lokal, Wertebereich 0-59),
    <rand2> = 2 Zufallsbytes. Ein STATISCHER Zeitsync (stundenalte Zeit) lässt die
    Box die Session nicht abschließen (kein Config-Report/Telemetrie) — v0.1.6/0.1.7
    blieben deshalb stumm. Der 39-B-Zeitsync (0x13 0x03 0x0b...) bleibt unverändert.
    """
    import os
    import time as _time

    now = _time.localtime()
    extra = os.urandom(2)
    return build(
        serial,
        b"\x00\x77\x00\x00\x12\xf8\x13\xa0\x0a\x01\x08\x02\x00\x08"
        + bytes([now.tm_sec, now.tm_min])
        + b"\x15\x1f\x0a\x1a\x06\x01"
        + extra
        + b"\xd0\x0d",
    )

def static_39(serial: bytes) -> bytes:
    """Statische 39-B-Meldung des echten Servers (Mitschnitt 2026-10-31).

    Der echte Server sendet dieses Frame bei jeder Session mehrfach (~alle 5 s);
    ohne es bleibt die Box offenbar im Wartezustand und schickt keine Daten.
    Bytes sind über alle Mitschnitte konstant — 1:1 vom Original übernommen.
    """
    return build(serial, bytes.fromhex("0077000013030ba00a010c010000915ed00d"))


def make_workmode(serial: bytes, mode: int, power_w: int) -> bytes:
    """mode: 16=Lastprio, 17=Batterieprio, 255=Shutdown; power 150..800 (min 150!)."""
    f = bytearray(WM_REST)
    f[WM_MODE_POWER_OFF] = mode & 0xFF
    f[WM_MODE_POWER_OFF + 1] = round(power_w / 8)
    return build(serial, bytes(f))

def make_dod(serial: bytes, dod_pct: int) -> bytes:
    f = bytearray(SB_REST)
    f[SB_DOD_OFF] = dod_pct & 0xFF
    return build(serial, bytes(f))
