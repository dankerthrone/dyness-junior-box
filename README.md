# Dyness Junior Box — lokale Steuerung & Home-Assistant-Integration

Die **Dyness Junior Box** (Balkonkraftwerk-Batterie) **lokal steuern und monitoren — ohne Dyness-Cloud**. Ergebnis einer Reverse-Engineering-Reihe an einem eigenen Gerät (2026-10-31):

- **Dylink-Protokoll (TCP 5005) entschlüsselt** — die Box verbindet sich aktiv zu `logger.dyness.com`; wer diesen Kanal nachahmt (Fake-Server/MITM), redet direkt mit der Box.
- **Steuerbefehl `00 78` geknackt**: Leistungslimit, Prioritätsmodus und Entladetiefe werden lokal gesetzt — die Box quittiert mit `91 78` und führt aus (gemessen: 200 W gesetzt → 183 W am Zähler; 150 W → 138 W).
- **Home-Assistant-Integration** (`custom_components/dyness_junior`) — Fake-Server läuft **in der Integration selbst**; Sensoren + Steuer-Services.

> ⚠️ **Sicherheit:** Leistungen **< 150 W werden von der Box als „unbegrenzt" behandelt** (Batterie-Leerlauf-Gefahr!). Die Integration erzwingt daher eine Untergrenze von 150 W.

## Installation (HACS)

1. HACS → Integrationen → ⋮ → Benutzerdefinierte Repositories
2. URL: `https://github.com/<dein-user>/dyness-junior-box` — Kategorie: **Integration**
3. Installieren → Neustart → „Dyness Junior Box (Local)" als Integration hinzufügen
4. **S/N des WiFi-Collectors** eintragen (ohne `-BMS`-Suffix, z. B. `R07E8546681A0121`)

### Wichtig: DNS-Umleitung (einmalig)

Die Box ruft aktiv `logger.dyness.com` auf (alle ~14 s). Damit sie **bei deiner HA-Instanz** anklopft, muss dieser Name auf die HA-IP zeigen, z. B. per DNS-Rewrite in AdGuard Home:

```
logger.dyness.com → <IP-der-HA>
```

Danach: Box einmal vom Strom nehmen (10 s) — sie verbindet sich innerhalb einer Minute mit HA. Die App zeigt die Box dann als „offline" (erwartet), die Integration als „verbunden".

## Services

| Service | Funktion | Parameter |
|---|---|---|
| `dyness_junior.set_workmode` | Leistungslimit + Prioritätsmodus | `power` (150–800 W), `mode` (16=Last-, 17=Batterieprio, 255=Shutdown) |
| `dyness_junior.set_dod` | Entladetiefe | `dod` (0–100 %) |

## Status

- ✔ Lokale Steuerung (Leistung/Modus/DOD) — an echter Hardware verifiziert
- ✔ Lokaler Server-Dialog komplett (Login/Bind/Zeitsync/Config/Telemetrie)
- 🚧 SOC-/Register-Semantik: experimentell (v0.2-Verifikation gegen Live-Referenz)
- 🚧 Cloud-Durchreiche-Modus (als Rückfallschalter) — geplant

## Repo-Layout

```
custom_components/dyness_junior/   HA-Integration (Server + Sensoren + Services)
  dylink/                          Protokoll-Bibliothek (frames, parser, server)
docs/                              Reverse-Engineering-Dokumentation (Roadmap, API, APK)
tools/                             Probe-/Analyse-Werkzeuge (dyness_probe, tcp_proxy, gen_frames …)
```

## Disclaimer

Inoffizielles Community-Projekt, ohne Gewähr, MIT-lizenziert. Alles basiert auf beobachtetem Verhalten eines eigenen Geräts; Firmware-Änderungen von Dyness können Teile des Protokolls unbrauchbar machen. Nutzung auf eigenes Risiko.