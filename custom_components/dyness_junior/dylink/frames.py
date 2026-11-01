"""Bequeme Frame-Builder um die generierten Templates (frames_gen.py)."""
from __future__ import annotations

from . import frames_gen as g


def serial_bytes(serial: str) -> bytes:
    return serial.encode("ascii")


def build_login_ack(serial: str) -> bytes:
    return g.login_ack(serial_bytes(serial))


def build_ack_telem(serial: str) -> bytes:
    return g.ack_telem(serial_bytes(serial))


def build_ack_cfgrep(serial: str) -> bytes:
    return g.ack_cfgrep(serial_bytes(serial))


def build_bind_ack(serial: str, token: bytes | None = None) -> bytes:
    if token is None:
        import time

        token = (int(time.time()) & 0xFFFFFF).to_bytes(3, "big")
    return g.bind_ack(serial_bytes(serial), token)


def build_time_push(serial: str) -> bytes:
    return g.time_push(serial_bytes(serial))


def build_static_39(serial: str) -> bytes:
    """Die vom echten Server wiederholte 39-B-Meldung (s. frames_gen.static_39)."""
    return g.static_39(serial_bytes(serial))


def build_workmode(serial: str, mode: int, power_w: int) -> bytes:
    """SetWorkModeSetting. mode 16/17/255; power 150..800 (Untergrenze!)."""
    return g.make_workmode(serial_bytes(serial), mode, power_w)


def build_dod(serial: str, dod_pct: int) -> bytes:
    """SetBaseSetting Entladetiefe (z. B. 95 = 5 % Rest)."""
    return g.make_dod(serial_bytes(serial), dod_pct)


BANNER = g.BANNER


def banner_framed() -> bytes:
    """Banner als längen-präfixierter Frame, wie der echte Server ihn sendet.

    Gemessen (2026-10-31, Relay-Mitschnitt): Wire = `00000053 00007f <text>`.
    Ein UNGERAHMT gesendeter Banner (nur '00 00 7f ...') wirkt für den
    Frame-Parser der Box wie ein 32-KB-Frame und blockiert ihren Dateneingang
    — die Box sendet dann keine Config-Reports/Telemetrie.
    """
    return len(g.BANNER).to_bytes(4, "big") + g.BANNER