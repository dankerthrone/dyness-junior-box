# tools/ — CLI gegen die Dyness-Cloud (und BLE)

## dyness_probe.py

Alle Reads und Writes gegen die offizielle Partner-Open-API.

```
Vorbereitung (einmalig):
  cp config.example.json config.json     # App ID + Secret eintragen (lokal, nie ins Repo!)
  # device_sn: eure BMS-S/N (Endung -BMS)

Lesen:   python3 dyness_probe.py deviceinfo | realtime | alarm | status | checkversion | bind
Schreiben:
  python3 dyness_probe.py set-workmode --power 300 --mode 16 --yes     # Lastpriorität 300 W
  python3 dyness_probe.py set-workmode --power 150 --mode 16 --yes     # zurück auf 150 W
  python3 dyness_probe.py set-base --work-mode 6 --power-limit 300 --discharge-depth 80 --yes

Roh-Antworten landen in out/.
```

**Regeln (aus Sicherheitsgründen im Code):**
- Writes verlangen `--yes` (Bestätigungsflag).
- `set-workmode` überschreibt **alle 4 Zeitplan-Gruppen** ohne Read-back — nur mit Bedacht.
- **Nie `--power` < 150 schreiben** → Fallback „unbegrenzt" (Batterie-Leerlauf). Mehr: `../docs/API.md`.

Abhängigkeiten: nur Python-Standardbibliothek.

## ble_probe.py

BLE-Erkundung der Box (GATT-Scan, Init-FED5, JBD-Reads, unbekannter Kanal). **ADRESSE vor Nutzung anpassen** (eigene MAC aus dem Scan). Aktueller Stand: Box erreichbar, antwortet aber nicht auf die bekannten Framings — siehe `../docs/ROADMAP.md` Phase 3b. Benötigt `pip install bleak` (Nutzer-Python).

## config.example.json

```
{
  "api_id": "HIER_APP_ID_EINTRAGEN",
  "api_secret": "HIER_APP_SECRET_EINTRAGEN",
  "device_sn": "HIER_BMS_SN_EINTRAGEN-BMS",
  "region": "eu"
}
```
`config.json` ist per `.gitignore` vom Repo ausgeschlossen — Credentials gehören nie in git.