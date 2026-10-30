# Ent-Clouden: DNS-MITM-Anleitung (Phase 3, Kandidat 2)

Ziel: Der WiFi-Logger (Collector) der Junior Box soll statt zum Dyness-Broker zu einem **lokalen MQTT-Broker** sprechen, damit wir seinen Datenverkehr sehen (und später steuern können).

Voraussetzungen:
- Home Assistant auf dem HA-Raspi (4B), HAOS mit Add-on-Speicher
- Fritz!Box als Router (im Beispiel 192.168.178.1)
- Ein ~30-Minuten-Fenster, in dem die Box vorübergehend „offline“ in der App sein darf

**Wichtiger Hinweis:** Keine Steuer-Writes während des Tests; die App zeigt die Box als offline (erwartet); alles ist innerhalb von Minuten umkehrbar (Schritt „Zurücksetzen“).

---

## Teil A — Diagnose: Welchen Wegweiser nutzt der Collector? (10 min)

Ziel: sehen, welche DNS-Adressen die Box tatsächlich anfragt — ohne schon umzulenken.

1. **HA-IP notieren** (HA → Einstellungen → System → Netzwerk).
2. **Add-on „AdGuard Home“ installieren** (HA → Einstellungen → Add-ons → Store → „AdGuard Home“ → Installieren → Starten).
3. In AdGuard Home (oberste Schaltfläche „Open Web UI“, Erst-Login siehe Add-on-Log):
   - Zwei Displays deaktivieren, nichts ist nötig — wichtig ist nur, dass **Query-Logging** an ist (Standard).
4. **Fritz!Box-DNS auf den Pi zeigen:**
   - Fritz!Box-UI (http://192.168.178.1) → **Heimnetz → Netzwerk → Netzwerkeinstellungen**
   - Abschnitt **„IP-Adressen“ / DNS** → bei „DNS-Server“ wählen: **„Andere DNS-Server aus dem Heimnetz verwenden“** (od. entsprechende Variante) → IP des HA-Pi eintragen → Übernehmen.
   - Hinweis: Das betrifft nur Geräte, die ihren DNS per Router beziehen (der Normalfall). Geräte mit fest eingetragenem DNS (z. B. manuell auf dns.adguard.com gestellt) ignorieren das — genau das testen wir damit.
5. **Box neu starten** (Strom trennen ~10 s, wieder an) und 2–3 Min warten.
6. **AdGuard-Query-Log prüfen:** Nach „192.168.178.69“ (der Collector) filtern.
   - **Sieht man Anfragen an Dyness-Hosts (z. B. `euiot.dyness.com`)?** → weiter mit Teil B. Notiert euch die Hostnamen!
   - **Keine Anfragen von .69?** → Der Collector nutzt einen festen DNS (Szenario B, siehe unten) — Teil B funktioniert dann nicht über diesen Weg.

---

## Teil B — Ablenken: Collector auf den lokalen Broker umleiten (10–15 min)

1. **Add-on „Mosquitto broker“ installieren** (HA-Add-on-Store) → Konfiguration öffnen:
   - `anonymous: true` (nur für den Test; wir sind im LAN) — oder gleich einen `logins`-Eintrag anlegen.
   - Starten. Im Add-on-Log erscheinen Verbindungen.
2. **In AdGuard Home eine Umschreib-Regel eintragen:**
   - Einstellungen → **DNS-Umschreibungen** → „Neue Umschreibung“:
     - **Domain: `logger.dyness.com`** (gemessen am 2026-10-30 im Query-Log; NICHT euiot! — die Box fragt logger an)
     - Antwort: `<HA-IP>` (die IP des Pi, z. B. 192.168.178.126) → Speichern.
   - Fundnotiz: `logger.dyness.com` läuft bei Aliyun (EU), Port **1883 offen** (plaintext-MQTT erreichbar), `euiot.dyness.com` teilt sich dieselbe Backend-Infrastruktur, ist aber der App-Kanal.
3. **Box erneut neu starten** (Strom weg ~10 s, an). 2–5 Min warten.
4. **Beobachten:**
   - Mosquitto-Add-on → **Log**: Taucht eine Verbindung vom Collector auf (CONNECT/PINGREQ/PUBLISH)?
5. **Ergebnis-Entscheidungsbaum:**
   - **(a) Verbindung auf 1883 + MQTT-Nachrichten** → Jackpot: Protokoll liegt im Klartext vor. Nächste Schritte: mit `mosquitto_sub -h <HA-IP> -t '#' -v` alles mitschneiden; Topics/Payloads kartieren; später `AT+MBWR`-Writes zum Collector nachbauen (e-Linter-Referenz: deye-inverter-mqtt).
   - **(b) Nur Verbindungsversuche zu 8883 (TLS)** → die Box will verschlüsselt. Zweite Runde: Mosquitto mit zusätzlichem TLS-Listener (selbstsigniertes Zertifikat). Akzeptiert der Collector das Zertifikat NICHT (Handshake bricht ab) → er prüft Zertifikate: MQTT-MIMT tot, Ausweichrouten: Firmware-RE oder RS485. Akzeptiert er es → weiter wie (a).
   - **(c) Gar kein Kontakt** → siehe Szenario B / Abschnitt „Nächste Ausweichrouten“.

---

## Zurücksetzen (Rollo-Back, jederzeit)

1. AdGuard-Home: Umschreib-Regel löschen (oder AdGuard deaktivieren).
2. Fritz!Box: DNS wieder auf „vom Internetanbieter“ (bzw. Standard) stellen.
3. Box neu starten → nach 1–3 Min meldet sie sich beim echten Dyness-Broker; App zeigt sie wieder online. (Falls die App länger „offline“ zeigt: einfach ein paar Minuten warten, die Cloud braucht ggf. einen Poll.)

---

## Szenario B — was, wenn die Box festen DNS nutzt?

Keine Queries von .69 im AdGuard-Log → der Collector ignoriert den Router-DNS.
- Dann hilft nur, den **konkreten Dyness-Host auf IP-Ebene** zu treffen — per NAT geht das mit der Fritz!Box nicht sinnvoll; Optionen:
  1. **BLE-Deep-Dive** (Dylink-Framing herauslösen; siehe ROADMAP Phase 3b) — die Box hat BLE erreichbar, antwortet bisher nur nicht auf rohe AT/JBD-Frames.
  2. **Provisioning-Modus abwarten:** Beim WLAN-Einrichten der Box dürfte der lokale WIFIKIT-Kanal offen sein (Phase-3-Befund) — dann wären `AT+IPMQSITE`-Befehle denkbar, um den Broker dauerhaft umzukonfigurieren.
  3. **RS485** an der Box (BMS-Modul werkzeuglos ziehbar, Garantie) — letzte, dafür zuverlässigste lokale Option.

## Hinweise fürs Repo

- Keine Secrets/S-N im Log verwenden; Screenshots ggf. schwärzen.
- Messprotokoll (was wurde wann getestet, Ergebnis a/b/c) ergänzt später den „Evidence“-Teil des Repos.