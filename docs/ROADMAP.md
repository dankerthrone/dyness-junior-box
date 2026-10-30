# Roadmap

Ziel: Steuerung der Dyness Junior Box maximal intelligent und, wo möglich, **ohne Hersteller-Cloud**; idealerweise als **Home-Assistant-Community-Plugin**.

## Status 2026-10-30

- ✅ **Phase 1 (Cloud-Kontrolle) im Kern erledigt:** Offizielle Open-API v2 steuert die Box nachweislich (modus 16 Lastpriorität, 150–800 W, Präzision ≈ Soll −14 W, greift < 60 s).
- ✅ APK-Analyse: Adress-Karte, Dylink-SDK, MQTT-Broker `euiot.dyness.com` (Port 1883 offen).
- ⏳ DOD-Test ausstehend (20-%-Boden: BMS-Schutz oder Parameter? `dischargeDepth` wird akzeptiert, Wirkung nur durch Entladung unter 20 % prüfbar).
- ⏳ Lokaler Zugriff (Ent-Clouden) offen.

## Phasen

### Phase 1 — Cloud-API-Kontrolle ✅ (weitgehend)
`tools/dyness_probe.py` + Doku. Offene Einzeltests: DOD-Wirkung, `SetBaseSetting`-workMode-Semantik im Zusammenspiel mit aktivem Zeitplan.

### Phase 2 — App-Mitgehören / Gateway-API (in Planung)
- Die App spricht `gateway.dyness.com/api/gateway` (BFF). Mit den normalen App-Zugangsdaten direkt ansprechen → vermutlich die „vollständigere" Steueroberfläche (alle App-Funktionen).
- Optional: Firebase-Projekt `dyness-ems-app-f73b2` als Laufzeit-Konfigurationsquelle auswerten.

### Phase 3 — Lokal (Ent-Clouden) — zwei Kandidaten
1. **Dylink-Lokal-Finder**: Die App findet den Collector beim WLAN-Setup lokal (UDP-Broadcast). Wenn der Collector auch im Normalbetrieb auf den Finder antwortet → lokaler Kanal ohne Router-Eingriff. Nächster Schritt: Broadcast-Format aus `libapp.so`-Strings/Disassembly extrahieren, Probe senden.
2. **DNS-MITM**: Eigener Resolver (AdGuard Home) + MQTT-Broker (mosquitto) auf dem HA-Raspi; nur `euiot.dyness.com` auf den Pi umlenken (FritzBox-Router-DNS). Da Port 1883 unverschlüsselt erreichbar ist: gute Chance auf Klartext-Protokoll. Braucht User-Grünlicht (Router-Eingriff).

### Phase 3b — BLE (bewertet: vorerst Sackgasse)
Erreichbar (Connect, GATT, MTU 247), aber stumm: Init `aa5501000056` auf FED5 + JBD-Reads (`dda50300fffd77` …) auf FE01 **und** auf dem undokumentierten Kanal `e31c42f9-…365a` → keine Antworten. App-Livedaten kommen vermutlich über die Cloud, nicht über BLE (Verdacht aus Community-Capture). Vertagt.

### Phase 4 — HA-Plugin (Zielbild)
- **Form:** Eigene HACS-Integration (Standalone „Dyness Junior Box Control") **oder** Fork/PR zu `shopf/dyness_battery` (bestehende Monitoring-Integration, MIT) — Monitoring ist dort gelöst, Steuerung nicht; unsere `SetWorkModeSetting`-Erkenntnisse wären der additive Kern.
- **Bausteine:** API-writes mit Wächter (niemals <150 W; Restore-Entity wie in `aistuartai/Dyness-Inverter-Control`); Live-Messung über vorhandene Leistungs-Sensoren (Tasmota/HA) statt API-Reads; Automation „100 %-SOC-Fall": bei SOC 100 + Sonne + Ausgang 0 → Setpoint nachschieben.
- **Safety:** zweistufiges Stage→Confirm für Schreib-Services; dokumentierte Fallbacks (App bleibt einzige Restore-Quelle für Zeitpläne).

## Nebenbefunde für die Doku

- Firmware ist nicht öffentlich ladbar (checkVersion = nur Versionen); OTA läuft cloud-seitig.
- Box führte 2026-10-30 Firmware `24.9-4.1.1`, BMS-Version `1014`.