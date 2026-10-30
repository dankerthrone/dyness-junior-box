# API-Protokoll — Dyness Junior Box (Open API v2)

Gemessener Stand, Basis: offizielle Doku `Dyness_Junior_Box_Open_API_Protocol_V1.0.pdf` (2026-04) + eigene Messungen (2026-10-30).

## Zugang

1. API-Key anlegen unter ems.dyness.com → Developer Center → API Management (App ID + App Secret, Secret nur einmal sichtbar).
2. Region EU: `https://eu-openapi.dyness.com/openapi/ems-device` (weitere: na/latam/me/af/sa/global/cn/apac).
3. **Signatur** (HMAC-SHA1), Header:

```
POST\n{Content-MD5}\napplication/json\n{Date}\n{path}
Authorization: API {apiId}:{sign}
Content-MD5: base64(md5(body))   # body: json.dumps(payload, separators=(',',':'), sort_keys=True)
Date: RFC-1123 GMT (z. B. "Fri, 30 Oct 2026 14:00:00 GMT")
```

4. Rate-Limit ≤ 2 Anfragen/Sekunde. `401` = Key-Aktivierung ausstehend ODER Unauthorized; `429` = Rate-Limit.

## Geräte-S/N — wichtige Unterscheidung

- **Nur die `-BMS`-S/N liefert Daten** (Gerätenummer des Batterie-Managers).
- Die Nummer **ohne Suffix** ist der WiFi-Collector (Loger): Antwort `code 500 "model does not support API access"` ist dort **Normalverhalten**, kein Fehler.

## Endpunkt-Katalog

| Endpunkt | Zweck | Pflichtfelder |
|---|---|---|
| `GET`/`POST`-Reads: | | |
| `/v2/GetDeviceInfBySN` | Geräte-Info | deviceSn |
| `/v2/GetRealTimeDataBySN` | Live-Batteriedaten | deviceSn |
| `/v2/GetAlarmInfBySN` | Alarme | deviceSn, pageNum, pageSize |
| `/v2/GetStatusInfBySN` | Betriebsstatus → bei Junior Box `data:null` (nicht nutzbar) | deviceSn |
| Writes: | | |
| `/v2/SetBaseSetting` | workMode (0 self-consumption, 1 off-grid, 3 economic, 6 battery priority), powerLimit W, dischargeDepth 0–100 | deviceSn + alle drei |
| `/v2/SetWorkModeSetting` | 4 workGroups: batteryWorkGroup 1–4, state 0/1, mode **16=Lastpriorität, 17=Batteriepriorität, 255=Shutdown**, startTime/endTime HH:mm, power 0–800, week 0–6 (CSV oder Bitmap) | deviceSn + workGroups[4] |

## Gemessenes Verhalten (wichtig!)

### Leistungslimit (`SetWorkModeSetting`, mode 16)

Setpoint-Treppe, verifiziert über Live-Stromzähler (Tasmota, Sekunden-genau):

| Setpoint | gemessen | Bewertung |
|---|---|---|
| 300 W | 287 W | ✓ präzise |
| 200 W | 183 W | ✓ präzise (PV wurde mitgedrosselt) |
| 150 W | 137 W | ✓ Untergrenze, funktioniert |
| **100 W** | **761 W** | ✗ **Fallback auf „unbegrenzt"!** |

- Das Limit wirkt auf die **Gesamt-Ausgangsleistung**; die Box drosselt dafür auch die PV.
- **150 W ist die harte Untergrenze — alles darunter bedeutet „kein Limit"** (Vollast + Batterieentladung). **Niemals < 150 W schreiben.**
- Writes greifen in ≤ 40 s (Cloud-Downlink). Nach einem abgelehnten/defekten Write sofort einen gültigen Wert nachschieben.

### Zeitplan (`SetWorkModeSetting`)

- **Alle 4 Gruppen müssen zusammen gesendet werden**; es gibt **keinen Read-back** (kein `GetWorkModeSetting`).
- Mit `--yes`-Schutz bedienen: Der App-Zustand ist die einzige Wiederherstellungsquelle.

### Reads & Aktualität

- **API-Reads sind bis zu 5 Minuten veraltet** (Cloud-Poll-Zyklus) — für Regelungen/Live-Anzeige unbrauchbar. Live-Referenz: eigener Messpunkt (Tasmota, Shelly, HA).
- `batteryStatus`: 0=Shutdown, 1=Standby, 2=Entladen, 3=Laden. Negative `batteryCurrent` = Entladen.
- `cellMax/cellMinVoltage` und Zelltemperaturen sind bei der Junior Box immer `0` (kein Zell-Detail über diesen Kanal).

## Fehlerbilder

- `code 500 "Some device serial numbers are not bound..."` → vorher `/v1/device/bindSn` (v1-Bereich, einmalig) aufrufen: `{deviceSn, collectorSn}`.
- `code 500 "The current device model does not support API access"` → Collector-S/N oder backend-seitig nicht freigeschaltetes Modell.
- Firmware-Versionen (`/v1/device/checkVersion`, v1): liefert nur Versionsnummern — **keine Download-URL** (Firmware ist nicht öffentlich ziehbar).

## Tooling

`tools/dyness_probe.py` — CLI (Reads: `deviceinfo|realtime|alarm|status|checkversion|bind`; Writes: `set-base`, `set-workmode`, nur mit `--yes`). Credentials aus lokalem `config.json` (nie im Chat/Repo). Roh-Antworten nach `out/`.