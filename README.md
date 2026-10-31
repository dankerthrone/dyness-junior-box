# Dyness Junior Box — lokale Steuerung & Home-Assistant-Integration

Die **Dyness Junior Box** (Balkonkraftwerk-Batterie) **lokal steuern und monitoren — ohne Dyness-Cloud**. Ergebnis einer Reverse-Engineering-Reihe an einem eigenen Gerät (2026-10-31):

- **Dylink-Protokoll (TCP 5005) entschlüsselt** — die Box verbindet sich aktiv zu `logger.dyness.com`; wer diesen Kanal nachahmt (Fake-Server/MITM), redet direkt mit der Box.
- **Steuerbefehl `00 78` geknackt**: Leistungslimit, Prioritätsmodus und Entladetiefe werden lokal gesetzt — die Box quittiert mit `91 78` und führt aus (gemessen: 200 W gesetzt → 183 W am Zähler; 150 W → 138 W).
- **Home-Assistant-Integration** (`custom_components/dyness_junior`) — Fake-Server läuft **in der Integration selbst**; Sensoren + Steuer-Services.

> ⚠️ **Sicherheit:** Leistungen **< 150 W werden von der Box als „unbegrenzt" behandelt** (Batterie-Leerlauf-Gefahr!). Die Integration erzwingt daher eine Untergrenze von 150 W.

## Installation (HACS)

1. HACS → Integrationen → ⋮ → Benutzerdefinierte Repositories
2. URL: `https://github.com/dankerthrone/dyness-junior-box` — Kategorie: **Integration**
3. Installieren → Neustart → „Dyness Junior Box (Local)" als Integration hinzufügen
4. **S/N des WiFi-Collectors** eintragen (ohne `-BMS`-Suffix, z. B. `R07E8546681A0121`)
5. **Dashboard (1 Klick):** Einstellungen → Dashboards → „+ Neu erstellen“ → **„Dashboard importieren“** → diese URL einfügen:
   `https://raw.githubusercontent.com/dankerthrone/dyness-junior-box/main/docs/dashboard.yaml`
   → Importieren. Fertiges Steuer-Dashboard (Status, Slider 150–800 W, Modus-Buttons).
   *Hinweis:* Zeigt eine Karte „nicht verfügbar“ (z. B. weil deine HA-Instanz der Box andere Entity-IDs gibt), die drei IDs unter **Einstellungen → Geräte & Dienste → Entitäten → Suche „dyness“** nachsehen und im Dashboard anpassen (Details: `docs/HA-Dashboard.md`).

   Eine Integration kann Dashboards **nicht automatisch** anlegen (HA bietet dafür keine Schnittstelle) — der Import ist der offizielle, ein-Klick-Ersatz.

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