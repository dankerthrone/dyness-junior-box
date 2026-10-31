#!/usr/bin/env python3
"""Dyness-Junior-Box-Dashboard auf der Home-Assistant-Instanz anlegen/aktualisieren.

Ein Befehl statt Karten-Gefummel im Roh-Editor — legt das Dashboard
(url_path 'dyness-junior-box') an bzw. ersetzt dessen Inhalt durch
docs/dashboard.yaml.

Nutzung (aus dem Repo-Verzeichnis):
    python3 tools/install_dashboard.py
    python3 tools/install_dashboard.py --url http://<ha-ip>:80 --token <MY-TOKEN>

Token: --token ARG, Umgebungsvariable HA_TOKEN oder Datei --token-file
(Default ~/.hermes/creds/ha_token). Tokens nie durch den Chat.
Abhaengigkeiten: websockets + pyyaml (pip install websockets pyyaml).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

try:
    import websockets
    import yaml
except ImportError as exc:  # pragma: no cover
    print(f"Fehlende Abhaengigkeit: {exc}", file=sys.stderr)
    print("  pip install websockets pyyaml", file=sys.stderr)
    sys.exit(2)

HERE = Path(__file__).resolve().parents[1]
DEFAULT_YAML = HERE / "docs" / "dashboard.yaml"
DEFAULT_URL = "http://192.168.178.126:80"
DEFAULT_SLUG = "dyness-junior-box"


async def run(args: argparse.Namespace) -> int:
    token = args.token or os.environ.get("HA_TOKEN")
    if not token and args.token_file:
        token = Path(args.token_file).read_text().strip()
    if not token:
        print("Kein Token: --token, HA_TOKEN oder --token-file setzen.", file=sys.stderr)
        return 1

    ws_url = args.url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
    config = {"views": yaml.safe_load(Path(args.yaml).read_text())["views"]}

    async with websockets.connect(ws_url, open_timeout=10, max_size=2**23) as ws:
        await ws.recv()  # auth_required
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        ack = json.loads(await ws.recv())
        if ack.get("type") != "auth_ok":
            print(f"Auth fehlgeschlagen: {ack}", file=sys.stderr)
            return 1

        _nid = 0

        async def call(cmd: str, **kw):
            nonlocal _nid
            _nid += 1
            await ws.send(json.dumps({"id": _nid, "type": cmd, **kw}))
            while True:
                r = json.loads(await ws.recv())
                if r.get("id") == _nid:
                    return r

        dash = await call("lovelace/dashboards/list")
        slugs = [d.get("url_path") for d in (dash.get("result") or [])]
        if args.slug in slugs:
            print(f"Dashboard '{args.slug}' vorhanden — Inhalt wird ersetzt.")
        else:
            print(f"Dashboard '{args.slug}' fehlt — wird per save angelegt (best effort).")
        r = await call("lovelace/config/save", url_path=args.slug, config=config)
        if r.get("success"):
            print("Erfolgreich gespeichert. Dashboard im HA-UI oeffnen (ggf. F5).")
            return 0
        print(f"FEHLER: {r.get('error')}", file=sys.stderr)
        return 1


def main() -> None:
    p = argparse.ArgumentParser(description="Dyness-Dashboard auf HA laden")
    p.add_argument("--url", default=DEFAULT_URL, help=f"HA-Basis-URL (Default: {DEFAULT_URL})")
    p.add_argument("--token", help="Long-Lived Access Token (alternativ HA_TOKEN)")
    p.add_argument("--token-file", default=str(Path.home() / ".hermes/creds/ha_token"))
    p.add_argument("--yaml", default=str(DEFAULT_YAML), help="Dashboard-YAML (Default: docs/dashboard.yaml)")
    p.add_argument("--slug", default=DEFAULT_SLUG, help="Dashboard-url_path")
    args = p.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()