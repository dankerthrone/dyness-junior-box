# APK-Analyse — angewandter Code-Befund

App: `com.dyness.emssmart` („Dyness", UI-Name), Version 3.4.2 (XAPK via APKPure-Spiegel, User-Download).
Artefakt-Pfad lokal: `~/dyness-apk/` (nicht im Repo; `findings/*.txt` = Auszüge).

## App-Technik

- **Flutter** (Google UI-Framework): 1117 `flutter_assets`-Dateien im Basispaket.
- Der eigentliche Programmcode (Dart) liegt **kompiliert** vor: `lib/armeabi-v7a/libapp.so` (48 MB) **in der Split-Datei `config.armeabi_v7a.apk`** — nicht im Basispaket (erstes Such-Hindernis).
- Kotlin/Java-Teil (`classes*.dex`): nur Dritt-Bibliotheken (okhttp, Firebase, Mapbox, PayPal) — **keine** Dyness-Endpunkte im Klartext.
- Konfiguration/Ressourcen: `resources.arsc` (Kotlin-Ressourcen-Datei), enthält u. a. Firebase-Referenzen und Push-Kanäle.

## Gefundene Adress-Karte (alle Hosts)

```
gateway.dyness.com        ← App-eigene API (EU), BFF: /api/gateway
apacgateway.dyness.com    ← API (Asien-Pazifik)
gateway.dyness.cn         ← API (China)
apacgateway…/gatewaydev.dyness.cn / gatewaytest.dyness.cn  ← Test/Dev
euiot.dyness.com          ← MQTT-Broker EU (IoT)       [Port 1883 offen, 8883 gefiltert — gemessen]
apaciot.dyness.com        ← MQTT-Broker APAC
partner.dyness.com / partnertest.dyness.cn  ← Partner-Portal
ems.dyness.com            ← Monitoring-Portal
web-static.dyness.com     ← Web-Builds
community.dyness.com      ← Community
aiapi.dyness.com          ← KI-API (Assistent?)
```

**Wichtig:** Die App spricht mit `gateway.dyness.com/api/gateway` — eine **andere Welt** als die Partner-Open-API (`eu-openapi.dyness.com`), mit der das Tooling dieses Repos arbeitet. Die Gateway-API ist eine „BFF" (Requests tragen die Operation im Body), nicht direkt aus den Dex-Strings ablesbar.

## „Dylink"-SDK — die Sprache der Box

Die App enthält ein eingebettetes IoT-SDK namens **Dylink** (`package:dylink/...`):

- `dylink_client.login.dart`, `DylinkLoginCommand`, `DylinkLogoutCommand`
- **`DylinkModbusWriteMessage`** → Steuer-/Statusnachrichten an den Collector laufen als **Modbus-artige Writes über MQTT**
- `DylinkOtaFlow`, `DylinkUpgradeBeginCommand`, `DylinkCollectorFirmwareVersionMessage`, `DylinkFirmwareAckMessage`
- Lokale WLAN-Provisionierung: `dylink_net_config_workflow.dart`, `DylinkNetConfigDeviceFinder`, `find_dylink_device_command` → **die App findet den Collector im LAN lokal** (UDP-Broadcast) und konfiguriert sein WLAN („Config Network" in der App)

Folgerung: Der WiFi-Logger (Collector) der Box spricht Dylink-MQTT gegen `euiot.dyness.com`. Für lokale Wege (DNS-MITM) ist das Ziel damit exakt benannt; für einen „lokalen Finder"-Weg ist das Provisioning-Protokoll der nächste Analysegegenstand (Format des Broadcasts ist noch unbekannt).

## Firebase

- Projekt: `dyness-ems-app-f73b2` (Firestore-Storage)
- Push-Kanäle: `dyness_push_high/low/medium/none/urgent`
- App-Konfiguration wird evtl. zur Laufzeit aus Firebase geliefert (Remote-Config-Charakter) — Erklärung dafür, dass Endpunkte nicht als Klartext in den Dex-Strings stehen.

## BLE-Seite (App-relevant)

- Die App hält `BLUETOOTH_CONNECT/SCAN`-Rechte — BLE wird genutzt (Provisioning/Lokalzugriff).
- Eigene Messung an der Box: GATT-Layout inkl. **undokumentiertem dritten Kanal** (`e31c42f9-…`) — Einzelheiten siehe `ROADMAP.md` (Phase 3) und lokale `ble_probe.py`-Erkenntnisse.