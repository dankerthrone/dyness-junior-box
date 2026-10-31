#!/usr/bin/env python3
"""Dylink-Fake-Server v5: kompletter Handshake + ACK auf Config-Rapport,
dann lauschen (Telemetrie erwartet)."""
import socket
import time

LOG = "/tmp/dylink_capture.log"
SN = b"R07E8546681A0121"

def log(msg):
    with open(LOG, "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    print(msg, flush=True)

BANNER    = b"\x00\x00\x00S" + b"\x00\x00\x7fThis is dyness.raymon service. node id is '00a9f0a9-7176-41b7-a1c5-0a5873849339'"
LOGIN_ACK = b"\x00\x00\x00\x14" + b"\x10" + SN + b"\x91\x00\x01"
BIND_ACK  = b"\x00\x00\x00\x1b" + b"\x10" + SN + b"\x91\x22\x00\x00\x01\xa1\x91\x1a\x19\x91"
CONFIG    = b"\x00\x00\x00\x29" + b"\x10" + SN + b"\x00\x77\x00\x00\x12\xf8\x13\xa0\x0a\x01\x08\x02\x00\x08\x0a\x24\x08\x1f\x0a\x1a\x06\x01\x07\x0b\xd0\x0d"
ACK_7191  = b"\x00\x00\x00\x14" + b"\x10" + SN + b"\x91\x71\x01"
ACK_71    = b"\x00\x00\x00\x14" + b"\x10" + SN + b"\x91\x00\x01"

def read_frame(c):
    try:
        h = c.recv(4)
    except Exception:
        return None
    if len(h) < 4:
        return None
    ln = int.from_bytes(h, "big")
    if not 0 < ln <= 8192:
        return None
    d = b""
    while len(d) < ln:
        try:
            ch = c.recv(ln - len(d))
        except Exception:
            break
        if not ch:
            break
        d += ch
    return h + d

srv = socket.socket()
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("0.0.0.0", 5005))
srv.listen(5)
log("Dylink-Fake-Server v5 (Handshake+Config-ACK) auf 5005")
counter = 0

while True:
    c, a = srv.accept()
    counter += 1
    c.settimeout(12)
    frames = []
    stage = "login"
    cfg_sent = 0
    try:
        for _ in range(60):
            fr = read_frame(c)
            if fr is None:
                break
            frames.append(fr)
            p = fr[4:]
            ln = len(p)
            if stage == "login" and ln >= 2 and p[0] == 0x10 and b"\x91\x00" in p[:24]:
                log(f"[{a[0]}] V#{counter} f0 LOGIN -> Banner+ACK")
                c.sendall(BANNER)
                c.sendall(LOGIN_ACK)
                stage = "bound?"
            elif stage == "bound?" and ln == 19 and p[0] == 0x10 and p.endswith(b"\x91\x22"):
                log(f"[{a[0]}] V#{counter} f1 BIND -> BindACK+Config")
                c.sendall(BIND_ACK)
                c.sendall(CONFIG)
                stage = "report"
            elif stage == "report" and ln > 200:
                # Config-Rapport der Box: je Kopie ein ACK-Kandidat
                cfg_sent += 1
                ack = ACK_7191 if cfg_sent % 2 == 1 else ACK_71
                log(f"[{a[0]}] V#{counter} Config-Rapport ({ln} B, #{cfg_sent}) -> {ack[4:].hex()}")
                c.sendall(ack)
            # alles weitere (Telemetrie?) wird nur protokolliert
    except Exception as e:
        log(f"err {e}")
    log(f"[{a[0]}] V#{counter} ENDE: {len(frames)} Frames | stage={stage}")
    for i, fr in enumerate(frames):
        p = fr[4:]
        show = p.hex() if len(p) <= 120 else p[:120].hex() + f"...(+{len(p)-120}B)"
        log(f"   f{i} ({len(p)}B): {show}")
    c.close()