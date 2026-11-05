"""Generierte Dylink-Templates — REST nach dem <SN>-Feld.
Regenerator: tools/gen_frames.py — NICHT von Hand editieren.

Die echte Geräte-S/N ist hier NICHT enthalten (Datenschutz, public repo). Die
eingebetteten SN-Positionen ([7] / [7])
werden zur Laufzeit von make_workmode/make_dod mit der Config-S/N gefüllt.
"""
from __future__ import annotations

WM_REST = bytes.fromhex("007836b200021000000000000000000000000000000000014a0ca97cb7a8700000000007000020d0491013000000001fa4497fff0000000021344902000000000022c449020000000000245449020000000000200849000000000000206c493709000000000000")
WM_MODE_POWER_OFF = 41
WM_EMBEDDED_SN_OFFS = [7]

SB_REST = bytes.fromhex("007836b200021000000000000000000000000000000000014a0ca97cb7a8700000000001000019c8495000000000000000")
SB_DOD_OFF = 41
SB_EMBEDDED_SN_OFFS = [7]

BANNER = b"\x00\x00\x7fThis is dyness.raymon service. node id is '00a9f0a9-7176-41b7-a1c5-0a5873849339'"

def build(serial: bytes, rest: bytes) -> bytes:
    body = b"\x10" + serial + rest
    return len(body).to_bytes(4, "big") + body

def login_ack(serial: bytes) -> bytes:
    return build(serial, b"\x91\x00\x01")

def ack_telem(serial: bytes) -> bytes:
    return build(serial, b"\x99\x04\x01")

def ack_cfgrep(serial: bytes) -> bytes:
    return build(serial, b"\x99\x71\x01")

def bind_ack(serial: bytes, token: bytes) -> bytes:
    return build(serial, b"\x91\x22\x00\x00\x01\xa1\x91" + token)

def time_push(serial: bytes) -> bytes:
    return build(serial, b"\x00\x77\x00\x00\x12\xf8\x13\xa0\x0a\x01\x08\x02\x00\x08\x00\x02\x09\x1f\x0a\x1a\x06\x01\x1c\x04\xd0\x0d")

def _inject_sn(rest_buf: bytearray, serial: bytes, offsets) -> None:
    for oi in (offsets or []):
        if oi + 16 <= len(rest_buf):
            rest_buf[oi:oi + 16] = serial

def make_workmode(serial: bytes, mode: int, power_w: int) -> bytes:
    f = bytearray(WM_REST)
    _inject_sn(f, serial, WM_EMBEDDED_SN_OFFS)
    f[WM_MODE_POWER_OFF] = mode & 0xFF
    f[WM_MODE_POWER_OFF + 1] = round(power_w / 8)
    return build(serial, bytes(f))

def make_dod(serial: bytes, dod_pct: int) -> bytes:
    f = bytearray(SB_REST)
    _inject_sn(f, serial, SB_EMBEDDED_SN_OFFS)
    f[SB_DOD_OFF] = dod_pct & 0xFF
    return build(serial, bytes(f))
