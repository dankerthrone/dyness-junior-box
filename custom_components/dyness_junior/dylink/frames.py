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


# 'Aus/Shutdown' — APP-MITSCHNITT 2026-11-02 (relay_shutdown_app_frame.log,
# 10:45:28, exakt 84 B payload). SetBaseSetting-Raster: 0x1900=workMode ff,
# 0x1964=Leistungsgrenze, 0x19C8=Entladetiefe. SetWorkMode-255 (`20 d0 49 ff`)
# ist WIRKUNGSLOS (bewiesen 02.11.) — nur dieser SetBaseSetting-Typ schaltet
# (potenziell) ab.
_SHUTDOWN_TEMPLATE = bytes.fromhex(
    "1052303738373536343638314130313231"
    "007836b200021052303738373536343638314130313231"
    "014a0ca97cb7a87000000000030000190049ff0000000000"
    "196449c8000000000019c8495000000000000000"
)
# SN-Feld-Positionen: 1..16 und 24..39 (nachgeprueft gegen den Mitschnitt)
_SHUTDOWN_SN_POS = (1, 24)


def build_shutdown(serial: str, power_w: int = 200, dod_pct: int = 80) -> bytes:
    """'Aus/Shutdown' — byte-genau aus dem App-Mitschnitt (2026-11-02, 84 B).

    00 78 36 b2 00 02 10 <SN> 01 4a 0c a9 7c b7 a8 70 00 00 00 03 00 00
      19 00 49 ff | 19 64 49 <power> | 19 c8 49 <dod>   (SetBaseSetting-Raster)

    0x1900 = workMode (ff = Shutdown), 0x1964 = Leistungsgrenze W,
    0x19C8 = Entladetiefe %. SN wird an beiden Feldpositionen ersetzt;
    power/dod per Zwischenschritt an den 0x19xx-49-Stellen (find-basiert).
    Quelle: ~/dyness-probe/relay_shutdown_app_frame.log
    """
    sn = serial_bytes(serial)
    if len(sn) != 16:
        raise ValueError(
            f"Shutdown frame requires a 16-byte serial, got {len(sn)} bytes "
            f"({serial!r}). Callers must validate length before calling."
        )
    _shutdown = bytearray(_SHUTDOWN_TEMPLATE)
    for pos in _SHUTDOWN_SN_POS:
        _shutdown[pos:pos + 16] = sn
    # power-Wert (3 Bytes nach dem 0x1964-49-Schluessel)
    off = _shutdown.find(b"\x19\x64\x49")
    if off >= 0:
        _shutdown[off + 3] = power_w & 0xFF
    # dod-Wert (3 Bytes nach dem 0x19C8-49-Schluessel)
    off = _shutdown.find(b"\x19\xc8\x49")
    if off >= 0:
        _shutdown[off + 3] = dod_pct & 0xFF
    assert len(_shutdown) == 84, f"Shutdown-Frame: {len(_shutdown)} B statt 84"
    return bytes(_shutdown)


BANNER = g.BANNER


def banner_framed() -> bytes:
    """Banner als längen-präfixierter Frame, wie der echte Server ihn sendet.

    Gemessen (2026-10-31, Relay-Mitschnitt): Wire = `00000053 00007f <text>`.
    Ein UNGERAHMT gesendeter Banner (nur '00 00 7f ...') wirkt für den
    Frame-Parser der Box wie ein 32-KB-Frame und blockiert ihren Dateneingang
    — die Box sendet dann keine Config-Reports/Telemetrie.
    """
    return len(g.BANNER).to_bytes(4, "big") + g.BANNER