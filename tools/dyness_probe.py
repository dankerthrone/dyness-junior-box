#!/usr/bin/env python3
"""
Dyness Junior Box — Open API v2 Probe (Phase 1)
Basiert auf: Dyness_Junior_Box_Open_API_Protocol_V1.0.pdf

Credentials werden aus config.json (NEBEN diesem Skript) gelesen —
niemals durch den Chat. config.json = Kopie von config.example.json.

Lesebefehle  : deviceinfo | realtime | alarm
Schreibtest  : set-base --work-mode <code> --power-limit <W> --discharge-depth <0-100> --yes
               (--yes ist Pflicht; sendet nur, was explizit angegeben wurde)
"""

import json
import os
import sys
import time
import base64
import hashlib
import hmac
import argparse
import urllib.request
import urllib.error
from email.utils import formatdate

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
OUT_DIR = os.path.join(BASE_DIR, "out")

REGIONS = {
    "eu1":    "https://open-api.dyness.com/openapi/ems-device",   # Europe v1 (checkVersion u. a.)
    "eu":     "https://eu-openapi.dyness.com/openapi/ems-device",
    "global": "https://global-openapi.dyness.com/openapi/ems-device",
    "na":     "https://na-openapi.dyness.com/openapi/ems-device",
    "latam":  "https://latam-openapi.dyness.com/openapi/ems-device",
    "me":     "https://me-openapi.dyness.com/openapi/ems-device",
    "af":     "https://af-openapi.dyness.com/openapi/ems-device",
    "sa":     "https://sa-openapi.dyness.com/openapi/ems-device",
    "apac":   "https://apacopen-api.dyness.com/openapi/ems-device",
}

def load_config():
    if not os.path.exists(CONFIG_PATH):
        sys.exit(f"Fehlende Datei: {CONFIG_PATH}\nBitte anlegen: cp config.example.json config.json und Credentials eintragen.")
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    missing = [k for k in ("api_id", "api_secret") if not cfg.get(k) or "HIER_" in str(cfg.get(k))]
    if missing:
        sys.exit(f"In config.json fehlen: {', '.join(missing)}")
    return cfg

def make_headers(cfg, path, body_bytes):
    content_md5 = base64.b64encode(hashlib.md5(body_bytes).digest()).decode()
    date = formatdate(usegmt=True)
    string_to_sign = f"POST\n{content_md5}\napplication/json\n{date}\n{path}"
    sig = base64.b64encode(
        hmac.new(cfg["api_secret"].encode(), string_to_sign.encode(), hashlib.sha1).digest()
    ).decode()
    return {
        "Content-Type": "application/json;charset=UTF-8",
        "Content-MD5": content_md5,
        "Date": date,
        "Authorization": f"API {cfg['api_id']}:{sig}",
    }

def api_call(cfg, path, body, tag, base=None):
    url = (base or REGIONS[cfg.get("region", "eu")]) + path
    body_bytes = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    headers = make_headers(cfg, path, body_bytes)
    os.makedirs(OUT_DIR, exist_ok=True)
    try:
        req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        status = e.code
    except Exception as e:
        raw = json.dumps({"code": "EXC", "info": str(e)})
        status = 0
    with open(os.path.join(OUT_DIR, f"{tag}.json"), "w") as f:
        json.dump({"status": status, "endpoint": path, "body": body, "response_raw": raw}, f, indent=2)
    print(f"── {tag}: {path}  [HTTP {status}]")
    print(raw)
    print()
    if status == 401:
        print("Hinweis: 401 laut Doku = 'Waiting for Key Activation' — API-Key evtl. noch nicht aktiviert.")
    if status == 429:
        print("Hinweis: 429 = Rate Limit (max. 2 Anfragen/Sekunde). Kurz warten und erneut versuchen.")
    time.sleep(1.3)  # Rate Limit: max 2/s
    return status

def variants(cfg):
    sn = cfg["device_sn"]
    cand = [sn]
    if sn.endswith("-BMS"):
        cand.append(sn[:-4])
    else:
        cand.append(sn + "-BMS")
    return cand

def main():
    ap = argparse.ArgumentParser(description="Dyness Junior Box Open API v2 Probe")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name in ("deviceinfo", "realtime", "alarm", "status", "checkversion", "bind"):
        sub.add_parser(name)

    sb = sub.add_parser("set-base")

    sw = sub.add_parser("set-workmode")
    sw.add_argument("--power", type=str, default="150", help="Leistungslimit in W (0-800), Standard 150")
    sw.add_argument("--mode", type=str, default="16", help="16=Lastpriorität, 17=Batteriepriorität, 255=Shutdown")
    sw.add_argument("--yes", action="store_true", help="Pflicht — bestätigt den Schreibtest")
    sb.add_argument("--work-mode", type=str, default=None, help="0: Self-consumption, 1: Off-grid, 3: Economic, 6: Battery priority")
    sb.add_argument("--power-limit", type=str, default=None, help="Leistungsbegrenzung in W")
    sb.add_argument("--discharge-depth", type=str, default=None, help="Entladetiefe 0-100")
    sb.add_argument("--yes", action="store_true", help="Pflicht — bestätigt den Schreibtest")

    args = ap.parse_args()
    cfg = load_config()

    if args.cmd == "deviceinfo":
        for sn in variants(cfg):
            api_call(cfg, "/v2/GetDeviceInfBySN", {"deviceSn": sn}, "deviceinfo")
    elif args.cmd == "realtime":
        for sn in variants(cfg):
            api_call(cfg, "/v2/GetRealTimeDataBySN", {"deviceSn": sn}, "realtime")
    elif args.cmd == "alarm":
        for sn in variants(cfg):
            api_call(cfg, "/v2/GetAlarmInfBySN", {"deviceSn": sn, "pageNum": 1, "pageSize": 20}, "alarm")
    elif args.cmd == "status":
        # Versuch, aktuellen Betriebsmodus/running state zu lesen (liefert bei manchen
        # Modellen delta: runModel, powerLimit, sparePower, workStatus, safeCountry)
        for sn in variants(cfg):
            api_call(cfg, "/v2/GetStatusInfBySN", {"deviceSn": sn}, "status")
    elif args.cmd == "checkversion":
        # v1-Endpunkt: fragt die Hersteller-Cloud, welche Firmware-Version für die Box
        # bereitsteht (Antwort kann eine Download-Adresse enthalten -> Firmware-RE-Quelle)
        for sn in variants(cfg):
            api_call(cfg, "/v1/device/checkVersion", {"deviceSn": sn}, "checkversion",
                     base=REGIONS["eu1"])
    elif args.cmd == "bind":
        # v1: Geräte-S/N an den API-Schlüssel binden (Voraussetzung für v1-Endpunkte wie checkVersion)
        sn_bms = cfg["device_sn"]
        sn_col = sn_bms[:-4] if sn_bms.endswith("-BMS") else sn_bms + "-BMS"
        api_call(cfg, "/v1/device/bindSn", {"deviceSn": sn_bms, "collectorSn": sn_col},
                 "bind", base=REGIONS["eu1"])
    elif args.cmd == "set-base":
        payload = {"deviceSn": cfg["device_sn"]}
        if args.work_mode is not None:
            payload["workMode"] = args.work_mode
        if args.power_limit is not None:
            payload["powerLimit"] = args.power_limit
        if args.discharge_depth is not None:
            payload["dischargeDepth"] = args.discharge_depth
        if len(payload) == 1:
            sys.exit("set-base braucht mindestens einen Wert (--work-mode, --power-limit oder --discharge-depth).")
        if not args.yes:
            sys.exit("Sicherheitshalber: --yes fehlt. Bitte erst lesen, dann bewusst schreiben.")
        print("ACHTUNG: Schreibe an die BOX:")
        print(json.dumps(payload, indent=2))
        print()
        api_call(cfg, "/v2/SetBaseSetting", payload, "setbase")
    elif args.cmd == "set-workmode":
        if not args.yes:
            sys.exit("Sicherheitshalber: --yes fehlt. Bitte erst lesen, dann bewusst schreiben.")
        off = {"batteryWorkGroup": 0, "state": "0", "mode": args.mode,
               "startTime": "00:00", "endTime": "00:00", "power": "0", "week": "0"}
        payload = {
            "deviceSn": cfg["device_sn"],
            "workGroups": [
                {"batteryWorkGroup": 1, "state": "1", "mode": args.mode,
                 "startTime": "00:00", "endTime": "23:59", "power": args.power,
                 "week": "0,1,2,3,4,5,6"},
                {**off, "batteryWorkGroup": 2},
                {**off, "batteryWorkGroup": 3},
                {**off, "batteryWorkGroup": 4},
            ],
        }
        print("ACHTUNG: Schreibe Zeitplan an die BOX (ersetzt Gruppen 1-4):")
        print(json.dumps(payload, indent=2))
        print()
        api_call(cfg, "/v2/SetWorkModeSetting", payload, "setworkmode")

if __name__ == "__main__":
    main()