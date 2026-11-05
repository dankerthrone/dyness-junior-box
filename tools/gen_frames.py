#!/usr/bin/env python3
"""Regeneriert frames_gen.py aus den Original-Mitschnitten.

Quellen:
  ctl_150.hex            — der byte-exakte SetWorkMode-Frame (124B, inkl. Praefix),
                           den die Box nachweislich mit 91-78 quittiert hat.
  relay_5005_full.log    — 2 SetBase-Frames (70B), die sich nur im DOD-Byte unterscheiden.

Aufruf: python3 tools/gen_frames.py
  (erwartet ~/dyness-probe/ctl_150.hex und ~/dyness-probe/relay_5005_full.log)

DATENSCHUTZ (2026-11-05): Die Geräte-S/N des Collector-Frames ist eine echte
Hardware-S/N. Sie wird beim Generieren aus den REST-Templates GEMASKT (durch
16 Nullen ersetzt) und NICHT ins Repo geschrieben. Die Builder (make_workmode /
make_dod) patchen die eingebettete SN-Position zur Laufzeit aus der HA-Config.
Damit liegt nie eine echte Geräte-S/N im Repository (public).
"""
from __future__ import annotations

import re
import sys

OUT = "custom_components/dyness_junior/dylink/frames_gen.py"


def mask_sn(rest: bytes, sn: bytes) -> tuple[bytes, list[int]]:
    """Ersetze jedes Vorkommen von `sn` in `rest` durch 16 Nullen.
    Gibt (maskiertes rest, Liste der Offsets) zurück."""
    offsets = []
    while True:
        j = rest.find(sn)
        if j < 0:
            break
        rest = rest[:j] + b"\x00" * 16 + rest[j + 16:]
        offsets.append(j)
    return rest, offsets


def main() -> int:
    try:
        wm = bytes.fromhex(open("/home/timon/dyness-probe/ctl_150.hex").read().strip())
        log = open("/home/timon/dyness-probe/relay_5005_full.log").read()
    except OSError as exc:
        print(f"Quellen nicht gefunden: {exc}", file=sys.stderr)
        return 1

    assert wm[:4] == b"\x00\x00\x00\x78" and wm[4] == 0x10, "WorkMode-Frame-Format"
    sn = wm[5:21]  # die (echte) S/N aus der Front des Captures
    if len(sn) != 16 or not sn.isalnum():
        raise SystemExit(f"unerwartete S/N-Länge: {len(sn)}")
    wm_rest = wm[21:]
    wm_rest, wm_sn_offs = mask_sn(wm_rest, sn)
    i = wm.find(b"\x20\xd0\x49")
    off = i + 3 - 21
    assert wm_rest[off:off + 2] == b"\x10\x13"

    sb = []
    for ln in log.splitlines():
        m = re.match(r"\[\d\d:\d\d:\d\d\] < (\d+)B: ([0-9a-f]+)", ln)
        if m and int(m.group(1)) == 70:
            sb.append(bytes.fromhex(m.group(2)))
    sb_rest, sb_sn_offs, sb_dod_off = b"", [], 41  # Defaults
    if not sb:
        print("WARNUNG: keine 70B-SetBase-Frames gefunden — DOD-Frames leer",
              file=sys.stderr)
    elif len(sb) < 2:
        print(f"WARNUNG: nur {len(sb)} SetBase-Frame(s)", file=sys.stderr)
    else:
        diffs = [j for j in range(len(sb[0])) if sb[0][j] != sb[1][j]]
        assert len(diffs) == 1 and sb[0][diffs[0]] == 0x50, diffs
        sb_rest, sb_sn_offs = mask_sn(sb[0][21:], sn)
        sb_dod_off = diffs[0] - 21
        assert sb_rest[sb_dod_off] == 0x50

    # SN-Patch-Ausdruecke fuer die generierten Builder:
    wm_patch = _sn_patch("WM_EMBEDDED_SN_OFFS", wm_sn_offs)
    sb_patch = _sn_patch("SB_EMBEDDED_SN_OFFS", sb_sn_offs)

    gen = f'''"""Generierte Dylink-Templates — REST nach dem <SN>-Feld.
Regenerator: tools/gen_frames.py — NICHT von Hand editieren.

Die echte Geräte-S/N ist hier NICHT enthalten (Datenschutz, public repo). Die
eingebetteten SN-Positionen ({wm_sn_offs or set()} / {sb_sn_offs or set()})
werden zur Laufzeit von make_workmode/make_dod mit der Config-S/N gefüllt.
"""
from __future__ import annotations

WM_REST = bytes.fromhex("{wm_rest.hex()}")
WM_MODE_POWER_OFF = {off}
{wm_patch}

SB_REST = bytes.fromhex("{sb_rest.hex()}")
SB_DOD_OFF = {sb_dod_off}
{sb_patch}

BANNER = b"\\x00\\x00\\x7fThis is dyness.raymon service. node id is '00a9f0a9-7176-41b7-a1c5-0a5873849339'"

def build(serial: bytes, rest: bytes) -> bytes:
    body = b"\\x10" + serial + rest
    return len(body).to_bytes(4, "big") + body

def login_ack(serial: bytes) -> bytes:
    return build(serial, b"\\x91\\x00\\x01")

def ack_telem(serial: bytes) -> bytes:
    return build(serial, b"\\x99\\x04\\x01")

def ack_cfgrep(serial: bytes) -> bytes:
    return build(serial, b"\\x99\\x71\\x01")

def bind_ack(serial: bytes, token: bytes) -> bytes:
    return build(serial, b"\\x91\\x22\\x00\\x00\\x01\\xa1\\x91" + token)

def time_push(serial: bytes) -> bytes:
    return build(serial, b"\\x00\\x77\\x00\\x00\\x12\\xf8\\x13\\xa0\\x0a\\x01\\x08\\x02\\x00\\x08\\x00\\x02\\x09\\x1f\\x0a\\x1a\\x06\\x01\\x1c\\x04\\xd0\\x0d")

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
'''
    with open(OUT, "w") as f:
        f.write(gen)
    print(f"OK — regeneriert in {OUT}; SN-Positionen WM={wm_sn_offs}, SB={sb_sn_offs}")
    return 0


def _sn_patch(name: str, offsets: list[int]) -> str:
    if offsets:
        return f"{name} = {offsets}"
    return f"{name} = []"


if __name__ == "__main__":
    raise SystemExit(main())