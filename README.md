# Dyness Junior Box — lokale Steuerung & Home-Assistant-Integration

Die **Dyness Junior Box** (Balkonkraftwerk-Batterie) **lokal steuern und monitoren — ohne Dyness-Cloud**. Ergebnis einer Reverse-Engineering-Reihe an einem eigenen Gerät (2026-10-31):

- **Dylink-Protokoll (TCP 5005) entschlüsselt** — die Box verbindet sich aktiv zu `logger.dyness.com`; wer diesen Kanal nachahmt (Fake-Server/MITM), redet direkt mit der Box.
- **Steuerbefehl `00 78` geknackt**: Leistungslimit, Prioritätsmodus und Entladetiefe werden lokal gesetzt — die Box quittiert mit `91 78` und führt aus (gemessen: 200 W gesetzt → 183 W am Zähler; 150 W → 138 W).
- **Basis-Modus-Read-back (v1.5.0):** der echte Modus (Register 0x1900, die vom App/SetBaseSetting geschriebene Ebene) wird live in der Modus-Select-Entity angezeigt; der Zeitplan-Modus bleibt protokollseitig unlesbar (ehrlich getrennt). **Experimentelle Temperatur-Sensoren** (`Temperature 1/2`) inklusive.
- **Home-Assistant-Integration** (`custom_components/dyness_junior`) — Fake-Server läuft **in der Integration selbst**; Sensoren + Steuer-Services.

> ⚠️ **Sicherheit:** Leistungen **< 150 W werden von der Box als „unbegrenzt" behandelt** (Batterie-Leerlauf-Gefahr!). Die Integration erzwingt daher eine Untergrenze von 150 W.

## Installation (HACS)

1. HACS → Integrationen → ⋮ → Benutzerdefinierte Repositories
2. URL: `https://github.com/dankerthrone/dyness-junior-box` — Kategorie: **Integration**
3. Installieren → Neustart → „Dyness Junior Box (Local)" als Integration hinzufügen
4. **S/N des WiFi-Collectors** eintragen (ohne `-BMS`-Suffix, z. B. `R0000000000000000`)
5. **Dashboard (1 Befehl):** auf einem Rechner im selben Netz aus dem Repo:
   `python3 tools/install_dashboard.py` (Token optional über `--token`/`HA_TOKEN`).
   Legt das Dashboard „Dyness Junior Box“ an bzw. aktualisiert es
   (Status, Slider 150–800 W, Modus-Buttons). Ohne Skript: manuell per
   Roh-Editor, siehe `docs/HA-Dashboard.md`.
   Ein Hinweis: Zeigt eine Karte „nicht verfügbar“, die drei Entity-IDs unter
   **Einstellungen → Geräte & Dienste → Entitäten → Suche „dyness“** nachsehen
   und anpassen.
   Eine Integration kann Dashboards **nicht automatisch bei der Installation**
   anlegen (HA bietet dafür keine Schnittstelle) — das Skript ist der
   ein-Befehl-Ersatz dafür.

### Wichtig: DNS-Umleitung (einmalig, ~2 Minuten)

**Warum das nötig ist:** Die Box ist nur ein Client — sie nimmt selbst keine Verbindungen an, sondern ruft von sich aus `logger.dyness.com` auf (alle ~14 Sekunden). Damit sie aber **bei deiner HA-Instanz** anklopft statt in der Dyness-Cloud, muss dieser Name auf die IP deiner HA zeigen. Diese Umleitung kann die Integration **nicht selbst einrichten** — sie ist Netzwerk-Sache. Du brauchst **keine neue Software**: Wer schon AdGuard Home (oder Pi-hole) im Netz hat, fügt dort nur eine Zeile hinzu. Das erledigt man **einmalig**, bei der Installation.

**Schritt für Schritt (AdGuard Home als Beispiel):**

1. Öffne die AdGuard-Oberfläche im Browser (z. B. `http://<IP-des-AdGuard>`).
2. Gehe auf den Tab **Filter** (nicht Einstellungen!) → Abschnitt **DNS-Umleitungen** → Klick auf **„DNS-Umleitung hinzufügen"** („Add DNS rewrite").
3. Trage ein:
   - **Domain:** `logger.dyness.com`
   - **Ziel:** die IP deiner Home-Assistant-Installation (z. B. `192.168.178.126` — achte darauf: die IP, unter der **HA** läuft, nicht die des AdGuard!)
4. Speichern. Danach die **Box einmal vom Strom nehmen (10 Sekunden)** und wieder einstecken — sie verbindet sich innerhalb von einer Minute mit HA.

**So prüfst du, ob es klappt:** In der Integration erscheint der Sensor **„Verbindung"** = *an*. Zusätzlich kannst du von einem Computer im Netz testen: `nslookup logger.dyness.com` → als Antwort muss die **HA-IP** erscheinen (statt einer Dyness-ServereIP).

**Erwartetes Ergebnis:** Die Dyness-App zeigt die Box danach als „offline" — das ist gewollt. HA (diese Integration) übernimmt jetzt die Rolle des Servers; die Box „lebt" lokal.

**Hinweis für Fortgeschrittene:** Statt AdGuard kannst du dieselbe Zuordnung auch am Router eintragen, sofern dieser Host-Überschreibungen (DNS-Override) kann — entscheidend ist nur: `logger.dyness.com` muss im ganzen Netz auf die HA-IP zeigen. (Eine Zukunftsidee des Projekts: statische Server-IP der Box direkt bei der Inbetriebnahme setzen — dann wäre die DNS-Regel verzichtbar.)

## Services

| Service | Funktion | Parameter |
|---|---|---|
| `dyness_junior.set_workmode` | Leistungslimit + Prioritätsmodus | `power` (150–800 W), `mode` (16=Last-, 17=Batterieprio, 255=Shutdown) |
| `dyness_junior.set_dod` | Entladetiefe | `dod` (0–100 %) |

## Status

- ✔ Lokale Steuerung (Leistung/Modus/DOD) — an echter Hardware verifiziert
- ✔ Lokaler Server-Dialog komplett (Login/Bind/Zeitsync/Config/Telemetrie)
- ✔ SOC/SOH/Spannung/Strom/Ausgangsleistung — gegen Cloud-API + Tasmota validiert
- 🚧 Temperatur-Sensoren — experimentell (Korrelation läuft)
- 🚧 Zeitplan-Modus-Read-back — nicht möglich über beobachtetes Protokoll
  (Basis-Modus 0x1900 ist der einzig real lesbare Modus-Zustand)
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