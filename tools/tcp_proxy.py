#!/usr/bin/env python3
"""Transparenter TCP-Stellvertreter mit bidirektionalem Mitschnitt.
Aufruf: python3 tcp_proxy.py <listen_port> <target_host> <target_port> <logfile>
Zeichnet beide Richtungen als Hex mit Zeitstempel auf (">" = client->server, "<" = server->client).
"""
import socket
import sys
import threading
import time

LPORT = int(sys.argv[1])
THOST = sys.argv[2]
TPORT = int(sys.argv[3])
LOG = sys.argv[4]

_lt = threading.Lock()

def log(msg):
    with _lt:
        with open(LOG, "a") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        print(msg, flush=True)

def pump(src, dst, tag):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
            log(f"{tag} {len(data)}B: {data.hex()}")
    except Exception:
        pass
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except Exception:
            pass

def handle(conn, addr):
    try:
        up = socket.create_connection((THOST, TPORT), timeout=10)
    except Exception as e:
        log(f"!! Verbindung zu {THOST}:{TPORT} fehlgeschlagen: {e}")
        conn.close()
        return
    log(f"Neue Verbindung {addr[0]}:{addr[1]} -> {THOST}:{TPORT}")
    t1 = threading.Thread(target=pump, args=(conn, up, ">"), daemon=True)
    t2 = threading.Thread(target=pump, args=(up, conn, "<"), daemon=True)
    t1.start(); t2.start()
    t1.join(); t2.join()
    conn.close()
    up.close()
    log(f"Verbindung {addr[0]} beendet")

srv = socket.socket()
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("0.0.0.0", LPORT))
srv.listen(16)
log(f"Proxy lauscht auf 0.0.0.0:{LPORT} -> {THOST}:{TPORT}")
while True:
    c, a = srv.accept()
    threading.Thread(target=handle, args=(c, a), daemon=True).start()