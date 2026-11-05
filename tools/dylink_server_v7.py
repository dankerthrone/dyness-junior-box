#!/usr/bin/env python3
"""Dylink-Fake-Server v7: zustandsloser Protokoll-Spiegel + 00-78-Injektion per Timer.
Jedes Box-Frame wird unabhaengig beantwortet (robust gegen jeden Frame-Ablauf);
Injektion via select-Loop (non-blocking)."""
import select
import socket
import time

LOG = "/tmp/dylink_v7.log"
SN = b"R0000000000000000"

def log(m):
    with open(LOG, "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {m}\n")
    print(m, flush=True)

def fr(p):
    return len(p).to_bytes(4, "big") + p

BANNER     = b"\x00\x00\x7fThis is dyness.raymon service. node id is '00a9f0a9-7176-41b7-a1c5-0a5873849339'"
LOGIN_ACK  = fr(b"\x10" + SN + b"\x91\x00\x01")
TIME_PUSH  = fr(b"\x10" + SN + b"\x00\x77\x00\x00\x12\xf8\x13\xa0\x0a\x01\x08\x02\x00\x08\x00\x02\x09\x1f\x0a\x1a\x06\x01\x1c\x04\xd0\x0d")
ACK_TELEM  = fr(b"\x10" + SN + b"\x99\x04\x01")
ACK_CFGREP = fr(b"\x10" + SN + b"\x99\x71\x01")

def bind_ack():
    tok = (int(time.time()) & 0xffffff).to_bytes(3, "big")
    return fr(b"\x10" + SN + b"\x91\x22\x00\x00\x01\xa1\x91" + tok)

# Steuerbefehl 1:1 aus Relay-Mitschnitt (0x00000078-Praefix + 124B Payload).
# Parameter-Paar "<mode> <p/8>" liegt bei Payload-Offset 58 (=Frame-Offset 62),
# hier "10 13" = mode16, 150W. 200W -> p/8 = 25 = 0x19.
_BASE = open("/tmp/ctl_150.hex").read().strip()
_B = bytes.fromhex(_BASE)
assert _B[62:64] == b"\x10\x13", _B[62:64].hex()
INJECT150 = _B
INJECT200 = _B[:62] + bytes([0x10, 0x19]) + _B[64:]

def handle(c, a, n):
    c.setblocking(False)
    buf = b""
    t0 = time.time()
    injected = False
    while time.time() - t0 < 45:
        # Injektion nach 6s (nur einmal pro Verbindung)
        if not injected and time.time() - t0 > 6:
            inj = INJECT150  # Test abgeschlossen: nur noch 150W-Restaure injizieren
            try:
                c.sendall(inj)
                log(f"V#{n} INJEKT 00-78 {'150W(Kanal-Test)' if n <= 3 else '200W'} -> warte auf 91-78")
                injected = True
            except Exception:
                pass
        r, _, _ = select.select([c], [], [], 1.0)
        if not r:
            continue
        try:
            d = c.recv(65536)
        except Exception:
            break
        if not d:
            break
        buf += d
        # Frames rausschaelen (4-Byte-Laengen-Praefix)
        while len(buf) >= 4:
            ln = int.from_bytes(buf[:4], "big")
            if not 0 < ln <= 8192:
                log(f"V#{n} kaputtes Frame (len {ln}), connection reset")
                return
            if len(buf) < 4 + ln:
                break
            p = buf[4:4 + ln]
            buf = buf[4 + ln:]
            tag = p[17:19] if len(p) > 19 else p
            if len(p) >= 2 and p[0] == 0x10 and b"\x91\x00" in p[:24] and len(p) < 100:
                c.sendall(BANNER); c.sendall(LOGIN_ACK)
                log(f"V#{n} login ({len(p)}B) -> banner+ack")
            elif len(p) > 400 and p[17:19] == b"\x91\x71":
                c.sendall(ACK_CFGREP)
                log(f"V#{n} config-report ({len(p)}B) -> 99 71 01")
            elif len(p) > 100:
                c.sendall(ACK_TELEM)
                log(f"V#{n} telemetrie ({len(p)}B) -> 99 04 01 | {p[:400].hex()}")
            elif p[17:19] == b"\x91\x22":
                c.sendall(bind_ack()); c.sendall(TIME_PUSH)
                log(f"V#{n} bind -> ack+zeitpush")
            elif tag == b"\x91\x87":
                log(f"V#{n} config-ack (91 87, {len(p)}B)")
            elif tag == b"\x91\x78":
                log(f"V#{n} >>> 91-78-ACK der Box!!! ({len(p)}B)")
            else:
                log(f"V#{n} sonstiges ({len(p)}B {tag.hex()})")
    c.close()
    log(f"V#{n} ENDE")

srv = socket.socket()
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("0.0.0.0", 5005))
srv.listen(5)
log("v7 bereit (zustandsloser Spiegel + Injektion)")
n = 0
while True:
    c, a = srv.accept()
    n += 1
    handle(c, a, n)