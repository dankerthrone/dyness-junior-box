# Dyness Junior Box — Community Control

Werkzeuge + Erkenntnisse zur Steuerung der **Dyness Junior Box** (1,6 kWh Balkonkraftwerk-Batterie) — basierend auf eigenen Messungen an einem Gerät, alles über die offiziellen Schnittstellen des Herstellers.

> ⚠️ **Status:** Aus Aus „Jailbreak"-Ziel wird „Integration": Die **offizielle Open-API v2 steuert die Box nachweislich**. Dieses Repo dokumentiert das gemessene Verhalten und liefert die Bausteine für eine Home-Assistant-Integration.

## Kurzfassung (deutsch)

| | |
|---|---|
| **Was geht** | Leistungslimit (150–800 W) + Betriebsmodus (Last-/Batteriepriorität) per Cloud-API setzen, Live-Daten lesen |
| **Was man wissen muss** | Werte **< 150 W werden als „unbegrenzt" interpretiert** (Batterie-Leerlauf-Gefahr!) — niemals schreiben |
| **API-Reads** | bis zu 5 Minuten veraltet (Cloud-Poll) — Live-Verifikation über eigenen Stromzähler nötig |
| **Offen** | DOD-Test (20-%-Boden?), lokaler Zugriff ohne Cloud (Ent-Clouden), HA-Plugin |

Details: [`docs/API.md`](docs/API.md) · [`docs/APK-Analyse.md`](docs/APK-Analyse.md) · [`docs/ROADMAP.md`](docs/ROADMAP.md)

## English summary

The Dyness Junior Box (balcony solar battery) **can be fully controlled through the manufacturer's official Open API v2** — power limit and operating mode (Load/Battery priority) via `SetWorkModeSetting`. Key measured facts:

- Output limit acts on **total output power**, the box curtails PV to match; measured 300→287 W, 200→183 W, 150→137 W (≈ −14 W conversion losses)
- **Hard floor: values below 150 W fall back to "unlimited"** (100 W → 761 W full output + battery drain). Never write < 150 W.
- API reads are **up to 5 min stale**; use a live meter (Tasmota etc.) for closed-loop control, API for writes only
- `SetWorkModeSetting` **overwrites all 4 schedule groups without read-back** — the app is the only restore source

## Repository layout

```
tools/                dyness_probe.py (+ ble_probe.py) — CLI gegen die Hersteller-Cloud bzw. BLE
docs/                 API-Protokoll, APK-Analyse, Roadmap
```

## License

MIT — siehe [LICENSE](LICENSE). (Community-Integrationen im HA-Ökosystem nutzen ebenfalls MIT.)