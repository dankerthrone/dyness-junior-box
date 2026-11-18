# Dyness Junior Box — lokale Steuerung & Home-Assistant-Integration

Die **Dyness Junior Box** (Balkonkraftwerk-Batterie) **ohne Dyness-Cloud** steuern und monitoren:
ein lokaler Server in der Integration übernimmt die Rolle von `logger.dyness.com` — Leistungslimit,
Prioritätsmodus, Entladetiefe und **echtes „Aus"** lokal gesetzt, Telemetrie (SOC/SOH/Spannung/
Strom/Ausgangsleistung/Temperaturen) live in Home Assistant. Alles an eigner Hardware gemessen
und verifiziert (Reverse Engineering, Stand 2026-11).

> ⚠️ **Sicherheit:** Leistungen **< 150 W behandelt die Box als „unbegrenzt"** (Batterie-Leerlauf-Gefahr).
> Die Integration erzwingt deshalb eine Untergrenze von 150 W.

## Installation

**HA ≥ 2026.11 (eingebauter Marketplace):** Einstellungen → Marketplace → ⋮ →
**Benutzerdefiniertes Repository** → URL `https://github.com/dankerthrone/dyness-junior-box`,
Kategorie **Integration** → installieren → HA-Neustart → **Dyness Junior Box (Local)** hinzufügen.
(Ältere HA-Versionen: gleicher Weg über HACS.)

Beim Hinzufügen die **S/N des WiFi-Collectors** eintragen (ohne `-BMS`-Suffix).

**Danach einmalig: DNS-Umleitung.** Die Box ist nur Client und ruft von sich aus
`logger.dyness.com` auf — damit sie bei deiner HA-Instanz anklopft, muss dieser Name auf die
**HA-IP** zeigen. Mit AdGuard Home (oder Pi-hole): **Filter → DNS-Umleitungen → hinzufügen:**
Domain `logger.dyness.com`, Ziel = IP deiner HA-Installation. Danach die **Box 10 s vom Strom**
— sie verbindet sich binnen einer Minute; der Sensor **„Verbindung"** wird *an*. Die Dyness-App
zeigt die Box fortan als „offline" — das ist gewollt. (Alternative: DNS-Override am Router;
Details + Fehlersuche: `docs/DNS-MITM.md`.)

**Dashboard (optional, 1 Befehl):** `python3 tools/install_dashboard.py` auf einem Rechner im
selben Netz (Token aus HA-Profil → Long-Lived Access Token, per `--token`/`HA_TOKEN`).
Manueller Weg: `docs/HA-Dashboard.md`.

## Steuerung

Über die Entities **Modus** (Lastpriorität / Batteriepriorität / Aus) und **Leistungsgrenze**
(150–800 W) oder per Service:

| Service | Funktion | Parameter |
|---|---|---|
| `dyness_junior.set_workmode` | Leistungslimit + Prioritätsmodus | `power` (150–800 W), `mode` (16=Last-, 17=Batterieprio, 255=Aus) |
| `dyness_junior.set_dod` | Entladetiefe | `dod` (0–100 %) |

## Status

- ✔ Lokale Steuerung (Leistung/Modus/DOD/**Aus**) — an echter Hardware verifiziert
- ✔ Telemetrie live (SOC/SOH/Spannung/Strom/Ausgangsleistung) — gegen Cloud-API + Tasmota validiert
- ✔ Echter Basis-Modus-Read-back (Register 0x1900)
- 🚧 Temperatur-Sensoren — experimentell; Zeitplan-Modus ist protokollseitig nicht lesbar

## Dokumentation

| Datei | Inhalt |
|---|---|
| `docs/REVERSE-ENGINEERING.md` | **Wie das Protokoll entschlüsselt wurde: Dylink-Handshake, Frame-Aufbau, Register-Karte, gemessenes Box-Verhalten, Werkzeuge** (für Contributors) |
| `docs/API.md` | Offizielle Cloud-Open-API v2 (Signatur, Endpunkte) |
| `docs/APK-Analyse.md` | App-Innenleben (Gateway, Dylink-SDK, Broker) |
| `docs/DNS-MITM.md` | DNS-Umleitung im Detail + Diagnose |
| `docs/HA-Dashboard.md` | Dashboard manuell einrichten |
| `docs/ROADMAP.md` | Projektphasen und Ausblick |

## Repo-Layout

```
custom_components/dyness_junior/   HA-Integration (Server + Sensoren + Services)
  dylink/                          Protokoll-Bibliothek (frames, parser, server)
docs/                              Dokumentation (s. oben)
tools/                             Probe-/Analyse-Werkzeuge (s. RE-Doku)
tests/                             pytest-Suite für Frames + Parser
```

## Disclaimer

Inoffizielles Community-Projekt, ohne Gewähr, MIT-lizenziert. Alles basiert auf beobachtetem
Verhalten eines eigenen Geräts; Firmware-Änderungen von Dyness können Teile des Protokolls
unbrauchbar machen. Nutzung auf eigenes Risiko.
