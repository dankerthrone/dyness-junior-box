# Reverse Engineering — Dyness Junior Box (Dylink-Protokoll)

Diese Datei dokumentiert den gemessenen Stand des lokalen Protokolls für alle, die
mitarbeiten oder die Ergebnisse nachvollziehen wollen. **Alles hier ist an echter
Hardware beobachtet/gemessen** (eigenes Gerät, 2026-10-30 bis 2026-11-18) — nichts ist
aus der Firmware geraten. Wo eine Aussage nur teilweise gesichert ist, steht es dabei.

Die kommentierte Chronologie der Untersuchung (was in welcher Reihenfolge versucht und
verworfen wurde) steht im Projekt-Worklog; hier steht das **kondensierte Ergebnis**.

## 1. Architektur der Box-Kommunikation

| Kanal | Richtung | Zweck |
|---|---|---|
| `logger.dyness.com:5005` (TCP) | Box verbindet sich **aktiv** (Client!) | „Dylink": Login, Telemetrie, Steuerbefehle. **Der einzig relevante Kanal.** |
| `cloud.raymoniot.com:9002` (HTTP plaintext) | Box → Cloud | Firmware-Versions-Check (`/prod-api/romRelease/checkVersion`) + konfigurierte API-Basis. Für vollständige Ent-Cloudung **ebenfalls** umleiten. |
| MQTT 1883 | — | **Totpfad**: von dieser Box nie beobachtet. |
| BLE / lokale AT-Befehle (UDP 48899/8899) | — | Nur im Provisionierungsmodus offen; im Normalbetrieb **keine offenen Ports an der Box** (Portscan-verifiziert). |

Kernpunkt: Die Box nimmt **nie** Verbindungen an — lokale Steuerung heißt daher immer
**MITM/Fake-Server**: DNS-Rewrite `logger.dyness.com` → IP des eigenen Servers, dort den
Server-Dialog nachspielen. Genau das tut die Integration (Server läuft im HA-Prozess).

Die Box verbindet sich im **~14-Sekunden-Zyklus neu** (normal!). Der echte Server schließt
Verbindungen nach ~12 s Leerlauf und wiederholt dabei Zeitsync + eine 39-B-Meldung ~alle 5 s.

## 2. Dylink-Framing

- Jedes Frame: **4-Byte-Längen-Präfix** (Big-Endian, Länge des gesamten Bodys) + Body.
- Body beginnt typischerweise mit `10 <16-Byte-S/N> <command> …`.
- **Lektion:** Ein Frame ohne Präfix kann von der Box nicht geparst werden — der anfangs
  vermutete „wirkungslose Shutdown" war in Wahrheit ein unpräfixiert gesendeter Frame
  (gefixt in v1.5.1).

## 3. Server-Antwortkette (Handshake)

Die Box liefert Telemetrie **nur**, wenn die Antwortkette des Servers vollständig ist;
fehlt ein Glied, sitzt sie in einer gehaltenen, leeren Session („verbunden", keine Daten).

1. Box → Login: `10 <SN> 91 00 solarhub solarhub@123456` (Default-Credentials des Collectors!)
2. Server → **Banner, gerahmt** (`4B-Präfix + 00 00 7f "<text>"`, 87 B). Ungerahmt gesendet
   wirkt er wie ein 32-KB-Schein-Frame und blockiert den Box-Eingang.
3. Server → Login-ACK `10 <SN> 91 00 01`
4. Box → Bind `10 <SN> 91 22` (**exakt 19 B** — Erkennung auf `>= 19`, nicht `> 19`!)
5. Server → BindACK `10 <SN> 91 22 00 00 01 a1 93 <3B-Token>` (**0xa1 0x93**, nicht 0x91)
   + **Zeitsync-Push** `00 77 00 00 12 f8 13 a0 0a 01 08 02 00 08 <sek> <min> 15 1f 0a 1a 06 01 <2 zuf.> d0 0d`
   (Sekunde/Minute **dynamisch** aus der Serveruhr) + **39-B-Meldung**
   `00 77 00 00 13 03 0b a0 0a 01 0c 01 00 00 91 5e d0 0d` (konstant, alle ~5 s wiederholt)
6. Box → Config-Report `91 71 …` (~475 B, TL-Liste: MAC/Firmware/Hosts/DHCP/API-URL) → Server ACK `99 71 01`
   + direkt danach ein Zeitsync+39-B-Paar (Mitschnitt-Timing)
7. Box → Telemetrie-Frames → Server ACK `99 04 01`

**Toleranz-Befund (2026-11):** Die Box lief 13 Tage auch mit defekter Kette (fehlender
39-B-Push, eingefrorener Zeitsync, 0xa1-0x91) weitgehend normal — diese Bausteine sind
nicht lebensnotwendig, aber originaltreu implementiert (v1.5.2).

## 4. Steuerbefehl `00 78`

Server → Box, nach erfolgreichem Session-Aufbau. Box quittiert mit `10 <SN> 91 78 …`.
**Regel: ein 00-78-Write ohne 91-78-ACK wurde von der Box verworfen.**

### 4.1 SetWorkModeSetting (Zeitplan-Ebene), 124 B wire

Kopf `01 4a 0c a9 7c b7 a8 70 00 00 00 07 00 00`, dann 9-B-Register
`[key:2][tag 0x49][Wert:4][pad:2]`:

| Key | Inhalt (gemessen) |
|---|---|
| `0x20d0` | `<mode> <power/8>` — mode: 16=`0x10` (Lastprio), 17=`0x11` (Batterieprio); power = W/8 gerundet (150 → `0x13`) |
| `0x1fa4` | `7f ff …` — Wochenbitmap `0x7f` = alle 7 Tage + Aktiv-Flag |
| `0x2008` | Start `00:00` (HHMM) |
| `0x206c` | Ende `0x0937` = `23:59` (HHMM) |
| `0x2134` / `0x22c4` / `0x2454` | Wert `2` — Gruppen 2–4 deaktiviert |

Der Schreibbefehl **überschreibt alle 4 Gruppen ohne Read-back**; die App ist die einzige
Wiederherstellungsquelle. Wirkung in ≤ 40 s.

### 4.2 SetBaseSetting (Basis-Ebene): DOD + **der echte „Aus"-Weg**

- DOD: `19 c8 49 <dod>` (dezimal→hex: 80→`0x50`).
- **Aus/Shutdown (88 B wire, 84 B payload):** Kopf `… 03 00 00` + drei Register:
  **`0x1900` = workMode (`0xff` = Aus)**, `0x1964` = powerLimit, `0x19C8` = dischargeDepth.
  Von der App per Mitschnitt entschlüsselt (2026-11-02/05); Box ACKt `91 78` und stellt die
  AC-Abgabe nachweislich ein (133 W → 0,4 W, verifiziert 18.11.2026). Semantik: **keine
  AC-Einspeisung, die Box bleibt an** (PV-/Lademanagement läuft weiter).
- ⚠️ **Mode 255 im SetWorkMode-Raster (`20 d0 49 ff`) ist WIRKUNGSLOS** (mehrfach bewiesen,
  auch mit byte-identischem Original-Cloud-Frame): die Box ACKt, führt aber nicht aus.

## 5. Telemetrie: Frame-Typen und Register-Grid

**Grid (korrigiert 2026-11-05):** jeder Record ist **`[key: 4 Bytes BE][tag: 1 B][Wert: tag-abhängig]`** —
nicht `[key16][tag][4B]`. Tag-Breiten: `0x53`=int16 (2 B), `0x46`=float32 (4 B), `0x49`/`0x4C`=int32 (4 B).
Der Frame-Header ist je Länge verschieden; gemessene Grid-Starts: 475 B ≈ +55, **1082 B = +67, 1088 B = +69**
(`tools/analyze_frame_geometry.py` misst das empirisch).

| Frame (Payload) | Register | Inhalt | Kadenz |
|---|---|---|---|
| 475 B / 21r | — | Config-Report (MAC, FW, Hosts) — **keine Messwerte** | fast jeder Reconnect-Zyklus |
| **1082 B / 109r** | u. a. 0x0320, 0x04B0, 0x0258, 0x02BC, 0x17D4, 0x1770, 0x1900, 0x1AF4/0x1B58 | Kernwerte | ~4–5 min |
| **1088 B / 125r** | Zellspannungen ~3,3 V, 0x36B0/0x3520 (SOC-Duplikate), 0x300C=2, 0x4524, 0x4588 | Zell-Detail | ~4–5 min, oft als Paar mit 1082 B |

### Kalibrierte Register

| Register | Bedeutung | Sicherheit |
|---|---|---|
| `0x0320` | **SOC %** | validiert (Cloud + Entladekurve) |
| `0x04B0` | **SOH %** (konstant 100) | validiert |
| `0x0258` (float) | Batteriespannung V | validiert |
| `0x02BC` (float) | Batteriestrom A (negativ = entladen) | validiert |
| `0x17D4` (int32) | **AC-Ausgangsleistung W** | validiert gegen Tasmota; negative Werte = Import/Netto → Filter 0–10000 |
| `0x238C` | Nennkapazität (2000 Wh) | plausibel |
| `0x1900` | **Basis-WorkMode (16/17/255)** — die von App/SetBaseSetting geschriebene Ebene | validiert (springt live 16↔17↔255) |
| `0x1770` | **Bilanz-/Netto-Leistung, KEIN Sollwert** (springt unabhängig vom Soll) | widerlegt als Sollwert |
| `0x1AF4` / `0x1B58` | Temperaturen °C (steigen bei Entladung) | experimentell |
| `0x4588` | 128↔64, fiel auf 0 beim Shutdown — Funktion unbekannt | offen |

**Zwei Modus-Ebenen (wichtig):** (1) **Zeitplan** (SetWorkModeSetting) — protokollseitig
**nicht lesbar**, überschreibt die Basis, solange aktiv. (2) **Basis** (SetBaseSetting) —
lesbar über `0x1900`. Die Integration zeigt beide getrennt an; einzige „Quittung" für
Zeitplan-Writes ist der 91-78-ACK (Attribut `box_bestaetigung`).

## 6. Gemessenes Box-Verhalten (Verhaltensmodell)

- **Modus 16 (Lastpriorität) X W:** Box speist X W ein — PV zuerst, Fehlbetrag aus dem
  Akku, PV-Überschuss lädt den Akku. Soll − ~14 W Wandlungsverluste am Ausgang.
- **Modus 17 (Batteriepriorität) X W:** Akku lädt mit bis zu X W; PV-Überschuss darüber
  geht ans Haus. **Nachts = Lastdeckung:** die Box deckt die Haus-Grundlast aus dem Akku
  (gemessen ~130 W konstant über Stunden; 0,4 W bei keiner Last; >300 W bei Last, auch
  über dem Limit). Das ist Design, kein Bug — wer „nachts nichts ans Haus" will, braucht
  **Aus** (0x1900=ff), nicht Batterieprio.
- **150 W harte Untergrenze:** < 150 W wird als „unbegrenzt" behandelt (Akku-Leerlauf!). Nutzbar: 150–800 W.
- **Entladeboden ≈ 19–20 % SOC**, aber nicht deterministisch (last-/spannungsabhängig, BMS); einmal 13 % beobachtet.
- Ohne gültigen Zeitplan fällt die Box auf **unbegrenzt** zurück — nach defekten Writes sofort einen gültigen Wert nachschieben.
- Nach einem **Power-Cycle** kann die Box mit verändertem Ausgangsverhalten zurückkommen → Soll-Zustand neu setzen.
- DOD greift grundsätzlich, **aber nicht unter aktivem Zeitplan** (Zeitplan übersteuert die Basis).
- Die Box entlädt auch ohne erreichbare Cloud weiter (persistiert ihre Einstellungen).

## 7. Werkzeuge (Reproduktion & Analyse)

| Werkzeug | Zweck |
|---|---|
| `tools/tcp_proxy.py` | Transparentes Relay Box↔echte Cloud mit bidirektionalem Hex-Mitschnitt (Text-Log `[HH:MM:SS] > 404B: <hex>`). ⚠️ kürzt große Frames im Log — Präfix-Länge gilt, nicht die Log-Bytezahl. |
| `tools/dyness_probe.py` | Offizielle Cloud-Open-API v2 (Reads `deviceinfo/realtime/alarm`, Writes `set-base`/`set-workmode` mit `--yes`). Credentials lokal in `config.json` (nicht im Repo). |
| `tools/dylink_server_v7.py` | Zustandsloser Fake-Server (Referenz-Handshake) + 00-78-Injektion. |
| `tools/gen_frames.py` | **Regeneriert `dylink/frames_gen.py`** aus den Original-Mitschnitten (maskiert die echte S/N durch Nullen). Nach jeder Regeneration das Funktions-Inventar diffen! |
| `tools/analyze_frame_geometry.py` | Misst Grid-Start + Register-Anzahl pro Frame-Länge empirisch. |
| `tests/` | pytest: Frame-Builder (Byte-Layouts) + Parser-Regression gegen echte Captures. |

**Verifikations-Dreiklang (immer so):** (1) `box_bestaetigung` (91-78-ACK) = Box hat den
Befehl geparst; (2) **Tasmota-Messsteckdose am Box-Ausgang** = Ground Truth für Leistung
(sekunden-live, ohne Auth: `curl "http://<tasmota>/cm?cmnd=Status%2010"` → `ENERGY.Power`);
(3) Register-Read-back (z. B. 0x1900) aus der Telemetrie. Der Cloud-API-Antwort nie trauen
(`500 NETWORK_ERROR` kam auch bei erfolgreicher Zustellung vor).

## 8. Bekannte Fallstricke

- **Sollwert-/Modus-Read-back:** gibt es nicht (s. 4/5) — Entities zeigen „zuletzt gesetzt" + ACK-Zeit; ehrlich so anzeigen statt raten.
- **uint32-Explosion:** negative int32 unsigned gelesen → ~4,29 Mrd. in Entities (Plausibilitätsfilter!).
- **Router-DNS-Cache (FritzBox):** antwortet aus eigenem Cache mit echten Dyness-IPs, obwohl
  der Rewrite-Server korrekt antwortet — Rewrite-Debug **immer per Direkt-Query an den
  Rewrite-Server** (`nslookup logger.dyness.com <IP-des-AdGuard>`), nie über den Router;
  nötigenfalls Router-Neustart.
- **Box-Backoff:** nach Fehlversuchen pausiert ihr TCP-Reconnect minuten- bis stundenlang,
  während ihre DNS-Queries weiterlaufen — DNS-Frische beweist keine Verbindungsbereitschaft.
  Abhilfe: Box-Power-Cycle (10 s).
- **HA-History-API liefert UTC** (lokal +1 h im Winter) — Phantom-Zeitpläne entstehen so.
- **Autodiscovery findet die Box nie** (reiner Client, kein mDNS) — manuell hinzufügen.

## 9. Offene Punkte (gute Einstiege für Contributors)

- `0x1770`-Semantik sauber benennen (Bilanz woran genau?), `0x4588` und weitere 1088er-Register zuordnen.
- Temperatur-Register `0x1AF4/0x1B58` final kalibrieren (Referenzthermometer).
- BLE-Kanal: GATT-Layout bekannt (FE00/FE01/FE02 + undokumentierter Service), Session-Handshake ungelöst.
- Zeitplan-RE der 4 Gruppen (Start/Ende/Woche schreiben statt konstante Defaults) — Vorsicht: kein Read-back.
- Cloud-Durchreiche-Modus (Relay als Fallback) in der Integration.
