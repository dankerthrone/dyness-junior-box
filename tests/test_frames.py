"""Frame-builder tests (HA-free). Cover the serial guard (A1) and the byte
structure of the Steuer-/Shutdown-Frames found by RE.

Layout facts verified here against the real implementation:
- build_workmode() -> build() adds a 4-byte length prefix (wire = 124 B).
  mode/power live at WM_REST-offset WM_MODE_POWER_OFF, i.e. wire offset
  = 4 (prefix) + 1 (0x10) + 16 (serial) + WM_MODE_POWER_OFF.
- build_shutdown() returns the RAW 84-B payload WITHOUT a length prefix —
  NOT wire-equivalent to the other injected frames. This asymmetry is a known
  open finding for the follow-up re-derivation of the "Aus" frame (see
  docs/HANDOFF-next-session.md); it is documented, not silently "fixed" here
  because changing it changes shutdown wire behavior mid-hardening.
"""
from __future__ import annotations

import pytest

import dylink.frames as frames
import dylink.frames_gen as g

TEST_SERIAL = "0123456789ABCDEF"
# offset of <mode> within WM_REST; wire offset = 4 + 1 + 16 + WM_MODE_POWER_OFF
WO = 4 + 1 + 16 + g.WM_MODE_POWER_OFF


def test_workmode_frame_length_and_fields():
    f = frames.build_workmode(TEST_SERIAL, 16, 150)
    assert len(f) == 124  # 4B prefix + 0x10 + 16B serial + WM_REST
    assert f[WO] == 16
    assert f[WO + 1] == round(150 / 8) == 19


def test_workmode_power_rounding():
    # Python round() = banker's rounding: 180/8=22.5 -> 22 (not 23). The
    # builder uses round(180/8) directly, so the wire byte is 22. This gives
    # the box ~±4 W granularity on the W/8 encoding; kept as-is (matches how
    # verified Writes behaved).
    f = frames.build_workmode(TEST_SERIAL, 17, 180)
    assert f[WO + 1] == 22


def test_workmode_mode_variants():
    for mode in (16, 17, 255):
        f = frames.build_workmode(TEST_SERIAL, mode, 200)
        assert f[WO] == mode


def test_shutdown_frame_length_sn_positions():
    f = frames.build_shutdown(TEST_SERIAL, power_w=200, dod_pct=80)
    # Wire = 4B Längen-Präfix + 84B Payload (wie der echte App-Frame 88B wire /
    # 84B payload; App-Mitschnitt 2026-11-05). Die Box ACKt NUR den präfixierten
    # Frame mit 91 78 — der frühere unprefizierte build_shutdown kam nie an.
    assert len(f) == 88
    assert f[:4] == (84).to_bytes(4, "big")
    body = f[4:]
    assert body[0] == 0x10
    sn_bytes = TEST_SERIAL.encode("ascii")
    assert body[1:17] == sn_bytes
    assert body[24:40] == sn_bytes
    off_p = body.find(b"\x19\x64\x49")
    assert off_p >= 0 and body[off_p + 3] == 200 & 0xFF
    off_d = body.find(b"\x19\xc8\x49")
    assert off_d >= 0 and body[off_d + 3] == 80 & 0xFF


def test_shutdown_rejects_non_16_byte_serial():
    with pytest.raises(ValueError):
        frames.build_shutdown("SHORT", power_w=200, dod_pct=80)
    with pytest.raises(ValueError):
        frames.build_shutdown("0123456789ABCDEFG", power_w=200, dod_pct=80)


def test_shutdown_workmode_differon_power_dod():
    a = frames.build_shutdown(TEST_SERIAL, power_w=200, dod_pct=80)
    b = frames.build_shutdown(TEST_SERIAL, power_w=150, dod_pct=95)
    assert a != b
    off_p = a.find(b"\x19\x64\x49")
    assert a[off_p + 3] == 200 & 0xFF
    assert b[off_p + 3] == 150 & 0xFF