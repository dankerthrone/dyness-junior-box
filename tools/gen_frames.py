#!/usr/bin/env python3
"""Regeneriert frames_gen.py aus den Original-Mitschnitten.

Quellen:
  ctl_150.hex            — der byte-exakte SetWorkMode-Frame (124B, inkl. Praefix),
                           den die Box nachweislich mit 91-78 quittiert hat.
  relay_5005_full.log    — 2 SetBase-Frames (70B), die sich nur im DOD-Byte unterscheiden.

Aufruf: python3 tools/gen_frames.py
  (erwartet ~/dyness-probe/ctl_150.hex und ~/dyness-probe/relay_5005_full.log)
"""
from __future__ import annotations

import re
import sys

OUT = "custom_components/dyness_junior/dylink/frames_gen.py"


def main() -> int:
    try:
        wm = bytes.fromhex(open("/home/timon/dyness-probe/ctl_150.hex").read().strip())
        log = open("/home/timon/dyness-probe/relay_5005_full.log").read()
    except OSError as exc:
        print(f"Quellen nicht gefunden: {exc}", file=sys.stderr)
        return 1

    assert wm[:4] == b"\x00\x00\x00\x78" and wm[4] == 0x10, "WorkMode-Frame-Format"
    assert wm[5:21] == b"R07E8546681A0121"
    wm_rest = wm[21:]
    i = wm.find(b"\x20\xd0\x49")
    off = i + 3 - 21
    assert wm_rest[off:off + 2] == b"\x10\x13"

    sb = []
    for ln in log.splitlines():
        m = re.match(r"\[\d\d:\d\d:\d\d\] < (\d+)B: ([0-9a-f]+)", ln)
        if m and int(m.group(1)) == 70:
            sb.append(bytes.fromhex(m.group(2)))
    assert len(sb) >= 2
    diffs = [j for j in range(len(sb[0])) if sb[0][j] != sb[1][j]]
    assert len(diffs) == 1 and sb[0][diffs[0]] == 0x50, diffs
    sb_rest, dod_off = sb[0][21:], diffs[0] - 21
    assert sb_rest[dod_off] == 0x50

    gen = f'''"""Generierte Dylink-Templates — REST nach dem <SN>-Feld.
Regenerator: tools/gen_frames.py — NICHT von Hand editieren.
"""
from __future__ import annotations

WM_REST = bytes.fromhex("{wm_rest.hex()}")
WM_MODE_POWER_OFF = {off}

SB_REST = bytes.fromhex("{sb_rest.hex()}")
SB_DOD_OFF = {dod_off}

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

def make_workmode(serial: bytes, mode: int, power_w: int) -> bytes:
    f = bytearray(WM_REST)
    f[WM_MODE_POWER_OFF] = mode & 0xFF
    f[WM_MODE_POWER_OFF + 1] = round(power_w / 8)
    return build(serial, bytes(f))

def make_dod(serial: bytes, dod_pct: int) -> bytes:
    f = bytearray(SB_REST)
    f[SB_DOD_OFF] = dod_pct & 0xFF
    return build(serial, bytes(f))
'''
    with open(OUT, "w") as f:
        f.write(gen)
    print(f"OK — regenerate in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())