#!/usr/bin/env python3
"""Empirische Frame-Geometrie-Analyse (Parser-Härtung, Task B).

Problem: parse_registers() läuft ab Byte 0 über das Payload und liest den
Frame-Header (0x10 + 16B S/N + cmd/Seq + ggf. zweite SN-Kopie) als "Register";
bei unbekannten Tags macht es `i += 1` -> 115r/116r Raster-Rutsch und verfälscht
Registerwerte (belegt: 0x17D4 281 W statt real 167 W).

Der Registerblock beginnt NICHT bei Byte 0, und der Header ist je Frame-Länge
verschieden. Dieses Skript misst je Frame-Länge (Payload-Präfix) empirisch den
GRID-START-OFFSET: den Offset, ab dem ein uniformer [key16][tag][4B] 7-Byte-Walk
maximal viele Register mit möglichst wenigen unbekannten Tags liefert — und
validiert ihn gegen die BEKANNTEN Register (0x0320 SOC, 0x04B0 SOH, 0x0258 V,
0x02BC A, 0x17D4 Ausgang, 0x1900 Basis-Modus).

Hinweis Mitschnitte: tcp_proxy-Logs sind für die großen Frames abgeschnitten
(Präfix sagt 1082/1088, auf Platte nur ~688B). Wir analysieren die VERFÜGBAREN
Bytes — genug, um den Grid-Start der führenden Register zu bestimmen.

Nutzung:  python3 tools/analyze_frame_geometry.py [relay-log ...]
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

TAGS = (0x46, 0x49, 0x4C, 0x53)
STRIDE = 7  # [key16][tag][4B]

# Bekannte/heikle Register zur Validierung des Grid-Starts
KNOWN = {0x0320, 0x04B0, 0x0258, 0x02BC, 0x17D4, 0x1900, 0x1770, 0x238C}


def extract_available(log_path: Path) -> list[bytes]:
    """Payload nach 4B-Präfix; falls Frame abgeschnitten, so viel wie da ist."""
    text = log_path.read_text(encoding="utf-8", errors="replace")
    pat = re.compile(r"\[(\d\d:\d\d:\d\d)\]\s*[<>]\s*(\d+)B:\s*([0-9a-fA-F ]+)")
    out = []
    for m in pat.finditer(text):
        raw = bytes.fromhex(m.group(3).replace(" ", ""))
        if len(raw) < 4:
            continue
        ln = int.from_bytes(raw[:4], "big")
        if not (0 < ln <= 8192):
            continue
        avail = min(len(raw) - 4, ln)
        if avail <= 100:
            continue
        payload = raw[4 : 4 + avail]
        if payload[:1] == b"\x10":
            out.append((ln, payload))
    return out


def walk(payload: bytes, start: int) -> dict:
    """7-Byte-Walk ab `start`; zähle Register, unbekannte Tags, Coverage."""
    n = len(payload)
    keys = []
    i = start
    unknown = 0
    last_ok = start
    while i + STRIDE <= n:
        key = int.from_bytes(payload[i : i + 2], "big")
        tag = payload[i + 2]
        if tag in TAGS:
            keys.append(key)
            last_ok = i + STRIDE
            i += STRIDE
        else:
            unknown += 1
            # versetzte Grid-Passage: einen Record überspringen, nicht 1 Byte
            i += STRIDE
    return {
        "keys": keys,
        "n": len(keys),
        "unknown": unknown,
        "covered": last_ok - start,
        "known_hits": len([k for k in keys if k in KNOWN]),
        "vals": {hex(k): int.from_bytes(
            payload[start + keys.index(k) * STRIDE + 3 :
                     start + keys.index(k) * STRIDE + 7], "big")
            if keys.index(k) * STRIDE + 7 <= len(payload) - start else "?"
            for k in keys if k in KNOWN},
    }


def best_grid(payload: bytes, max_start: int = 64) -> dict:
    best = None
    for s in range(max_start):
        r = walk(payload, s)
        # Score: möglichst viele Register, möglichst wenige unbekannte,
        # bekannte Register müssen getroffen werden.
        score = r["n"] - 5 * r["unknown"] + 50 * r["known_hits"] + r["covered"] * 0.01
        if best is None or score > best["score"]:
            r["score"] = score
            r["start"] = s
            best = r
    return best


def main() -> None:
    paths = [Path(a) for a in sys.argv[1:]] or [
        Path.home() / "dyness-probe/relay_5005_full.log",
        Path.home() / "dyness-probe/relay_shutdown_app_frame.log",
    ]
    by_len: dict[int, list] = defaultdict(list)
    for p in paths:
        if not p.exists():
            print(f"(!) fehlt: {p}")
            continue
        for ln, payload in extract_available(p):
            if ln > 300:
                by_len[ln].append(payload)

    print(f"Frame-Typen (Payload-Länge >300): {sorted(by_len)}")
    for ln, payloads in sorted(by_len.items()):
        unique = list(dict.fromkeys(payloads))[:6]
        starts = {}
        for payload in unique:
            b = best_grid(payload)
            starts.setdefault(b["start"], []).append(b)
        # Offset, der die meisten Samples minimal-unbekannt trifft
        rows = []
        for off, bs in starts.items():
            rows.append((off, len(bs), sum(x["n"] for x in bs),
                         sum(x["unknown"] for x in bs),
                         sum(x["known_hits"] for x in bs)))
        rows.sort(key=lambda r: r[4], reverse=True)
        print(f"\n  {ln}B ({len(payloads)} Frames, {len(unique)} Proben)")
        for off, nsamples, tot_n, tot_unk, tot_hit in rows[:5]:
            print(f"    Grid-Start +{off}: {nsamples} samples, "
                  f"{tot_n} Records, {tot_unk} unbekannt, {tot_hit} bekannte-Register-Treffer")
        # Beispiel-Registerwerte für den besten Offset
        b0 = best_grid(unique[0])
        print(f"    Beispiel (+{b0['start']}) bekannte Werte: {b0['vals']}")


if __name__ == "__main__":
    main()