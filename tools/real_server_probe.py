#!/usr/bin/env python3
"""Replayt den kompletten Collector-Start gegen den ECHTEN Dylink-Server
(logger.dyness.com:5005 -> IP direkt, DNS-Rewrite umgehen) und zeichnet dessen
Antworten auf jede Phase auf."""
import socket
import time

IP = "8.211.25.186"
SN = b"R0000000000000000"

def frame(payload):
    return len(payload).to_bytes(4, "big") + payload

LOGIN = frame(b"\x10" + SN + b"\x91\x00solarhubsolarhub@123456")
F1    = frame(b"\x10" + SN + b"\x91\x22")
with open("/home/timon/dyness-probe/f2_full.hex") as fh:
    F2 = bytes.fromhex(fh.read().strip())
assert len(F2) - 4 >= 450, len(F2) - 4  # Config-Rapport: Laenge variiert leicht (471-475)

def readf(s):
    try:
        h = s.recv(4)
    except Exception:
        return None
    if len(h) < 4:
        return None
    ln = int.from_bytes(h, "big")
    d = b""
    while len(d) < ln:
        try:
            ch = s.recv(ln - len(d))
        except Exception:
            break
        if not ch:
            break
        d += ch
    return h + d

def phase(s, label, data, read_n=4, wait=0.4):
    s.sendall(data)
    time.sleep(wait)
    out = []
    for _ in range(read_n):
        f = readf(s)
        if f is None:
            break
        out.append(f)
    print(f"\n== {label} ({len(data)-4} B gesendet) -> {len(out)} Antwortframe(s)")
    for f in out:
        p = f[4:]
        show = p.hex() if len(p) <= 160 else p[:160].hex() + f"...(+{len(p)-160}B)"
        print("   ", show, "|", p if len(p) < 100 else "")
    return out

s = socket.create_connection((IP, 5005), timeout=8)
s.settimeout(6)
phase(s, "LOGIN", LOGIN)
phase(s, "F1 (bind)", F1)
phase(s, "F2 (config-report)", F2, read_n=6, wait=1.0)
print("\n== 60s Leerlauf: was pusht der Server? ==")
start = time.time()
while time.time() - start < 60:
    f = readf(s)
    if f is None:
        time.sleep(0.5)
        continue
    p = f[4:]
    stamp = time.strftime("%H:%M:%S")
    show = p.hex() if len(p) <= 160 else p[:160].hex() + f"...(+{len(p)-160}B)"
    print(f"  [{stamp}] Server-Frame ({len(p)}B): {show}")
s.close()
print("\nFertig.")