# Handoff — nächste Session: Dashboard-Aufräumen + Temperatur-Sensoren

Stand 2026-11-01 MITTAG — **v1.0.0 (Major!): Steuerung + Monitoring sind als bewiesen markiert.** Alle Sensoren live, Steuerung ent-cloudt (00-78 → Tasmota-Verifikation), Frame-Typen getrennt. **Heutige Durchbrüche:** (1) **Frame-Längen-Schlüssel:** echte Telemetrie-Frames sind 1082 B (115 Register: SOC/SOH/Spannung/Strom/0x17D4-Ausgang/CAPACITY…) und 1088 B (123 Register: Zellspannungen, SOC-Duplikate 0x36B0/0x3520, Temperaturen, 0x4588 128↔64). (2) **0x1770 enttarnt — KEIN Sollwert:** Bilanz-/Netto-Leistung, springt −244…+18 W bei FESTEM Soll 150/200 W (Wert folgt Writes NICHT); Plausibilitäts-Filter (150–800) schluckt den Megawatt-Unsinn (User-Befund „5-MW-Skala" = −169 W unsigned gelesen). (3) **Modus-Read-back nicht in der Telemetrie:** 0x1900 blieb bei Mode-17-Test 16 (4×1082er-Sichtungen); sichtbarer Modus-Unterschied ist real (Tasmota 134→323 W bei Mode 17/Last-Deckung→0,4 W), aber KEIN Register meldet ihn. → **v1.0.0-Ansatz: 91-78-ACK der Box = der einzige nachweisbare Read-back** (Attribut `box_bestaetigung` an Modus+Leistungsgrenze; Config-Report 91 71 wird ab sofort auch als Register best-effort gescannt — letzter möglicher Ort). (4) 0x17D4 = Ausgangsleistung VERIFIZIERT (Tasmota 323↔336 W synchron). (5) Tasmota misst STABILEN Box-Ausgang (14 Messungen: 133,6–136,0 W), Netto-Schwankungen sind Wetter/PV-bedingt (Batterie puffert; current +19 A…−1,6 A).

**Nächste Goals: (1) Dashboard-Karten — ERLEDIGT (11:35, docs/dashboard.yaml neu: SOC-/Ausgangs-Gauges, Messwerte, Steuerung, Diagnose, aktualisierte Hinweise; per tools/install_dashboard.py auf HA gespeichert, alle 10 Entity-IDs live-verifiziert)** — Sichtcheck vom User offen, **(2) Temperatur-Sensoren** (0x1AF4/0x1B58 + 0x47E0/0x48A8/0x4A38/0x4B00 = 65,0 konstant, 0x4A9C=−20,0 — experimentell), (3) Config-Report-Register-Scan — ERLEDIGT (leer), (4) nocode-GUI (Backlog).

## Wo steht was (Gedächtnis der Maschine)

| Ort | Inhalt |
|---|---|
| `~/dyness-junior-box/` | Repo `dankerthrone/dyness-junior-box` (public). Integration in `custom_components/dyness_junior/`, Protokoll-Lib in `dylink/`, Doku in `docs/`, Werkzeuge in `tools/` |
| `~/dyness-probe/` | lokale Probe-Werkzeuge + Mitschnitte (`dyness_probe.py` Cloud-API, Creds in `config.json` — **nie durch den Chat**; `ctl_150.hex` Frame-Quelle) |
| `~/WORKLOG.md` + Joplin-Notiz `9dc077a80f4a48fa87a28c89c64b8824` | kompletter Tageslauf |
| Skill `dyness-junior-box` | Protokoll-Referenz (Dylink, 00-78, Register, IPs) — **beim Session-Start laden** |
| MM = 192.168.178.146 | Raspi 3B+; Relays sind GESTOPPT — nur HA (.126) bedient die Box |

## Wahrheitstabelle (Stand 11:xx — alles an echter Hardware gemessen)

- Box = Client auf `logger.dyness.com:5005` (Dylink, 4-Byte-Längen-Frames, ~14-s-Reconnect). MQTT/1883 = Totpfad.
- Login `10 <SN> 91 00 solarhub solarhub@123456` → Banner + `10 <SN> 91 00 01`. Bind `91 22` → BindACK `a1 93`. Config-Report `91 71` → `99 71 01`. Telemetrie → `99 04 01`. Steuerbefehl `00 78` → Box-ACK `91 78`.
- **Telemetrie-Frame-Typen (v1.0.0, Frame-Längen-Schlüssel `ln`):** 1082 B/115r = SOC(0x0320), SOH(0x04B0), Spannung(0x0258), Strom(0x02BC), Ausgang(0x17D4), 0x1900(=16 konstant), 0x1770(=Bilanz, KEIN Sollwert); 1088 B/123r = Zellspannungen (~3,3 V), SOC-Duplikate 0x36B0/0x3520, Temperaturen, 0x300C=2, 0x4524=14, 0x4588=128/64. Kadenz: je Typ ~alle 4-5 min, i. d. R. als Paar.
- **0x1770 = Bilanz-/Netto-Leistung** (negativ/positiv, springt unabhängig vom Soll) — der frühere „Sollwert-Read-back" (v0.1.7) war eine Fehlinterpretation eines anderen Frame-Kontexts.
- **Kein Modus-/Sollwert-Register in der Telemetrie gefunden** (0x1900, 0x300C, 0x4524, 0x4588 alle konstant über Mode-16/17-Tests). Einziger Read-back = 91-78-ACK (v1.0.0-Attribut `box_bestaetigung`).
- Steuerbefehl: SetWorkMode `20 d0 49 <mode> <p/8>` (16→`10`, 17→`11`, 255→`ff`; p = W/8, 150→`13`); SetBase-DOD `19 c8 49 <dod>`.
- **150 W harte Untergrenze** (< 150 = „unbegrenzt", Akku-Leerlauf!).
- Mode 17 = Last-Deckung: Ausgang folgt der Momentanlast (0,4 W bei keiner Last; 323 W bei Last), über das Limit hinaus — Testfenster-Fallstrick.
- DOD 95 greift (nachts bis 13 %). Tasmota 192.168.178.119 misst den Box-Ausgang stabil (Soll − ~15 W Verluste; Assembly: ±3 W Messrauschen, KEINE Netto-Sprünge).
- Box-Power-Cycle = 10 s Strom weg; bei Backoff-Dauern nur Power-Cycle hilft.

## Testplan nächste Session (Reihenfolge)

1. **Skill laden:** `skill_view(dyness-junior-box)` falls komprimiert.
2. **v1.0.0-HACS-Update** (falls ausstehend): HACS → Integrationen → Dyness → ⋮ → Re-download; HA-Restart per Service `homeassistant.restart` (HTTP 000 = erwartet).
3. ~~Config-Report-Register-Scan~~ — **ERLEDIGT (v1.0.0, 11:26):** 475B/21r in frame_stats, Interesse-Register = **leer** → kein Modus-/SOC-/Sollwert-Register im Config-Report. **Kein Frame meldet den Modus — Punkt 1 ist abgeschlossen, ACK-Read-back ist die Lösung.**
4. **Dashboard-Aufräumen (User-Wunsch):** `docs/dashboard.yaml` + `docs/dashboard-cards.yaml` pflegen (SOC-/Ausgangsleistungs-/Spannungs-Karten), `tools/install_dashboard.py` ausführen, Entity-IDs gegen `/api/states` abgleichen (nie raten!).
5. **Batterieprio-Semantik final verifizieren (User-App-Zeugnis, braucht Sonne):** Batterieprio + X W setzen → PV-Leistung im Steigen beobachten (Tasmota/current) → ab welchem PV-Wert springt der Ausgang an? Erwartung (User): Überschuss-Einspeisung ab PV > X (bzw. evtl. erst X + ~150 W Delta, Akku-Minimum). Damit 150-W-Delta-Regel belegen/widerlegen — Skill-Baustein danach endgültig absichern.
6. **Temperatur-Sensoren:** 0x1AF4/0x1B58 (Telemetrie?) + großes 1088er-Raster (0x47E0/0x48A8/0x4A38/0x4B00 = 65,0; 0x4A9C = −20,0) — Werte über Zeit gegen SOC/Strom korrelieren; dann Sensoren in sensor.py.
7. **Falls Zeit:** nocode-Automations-GUI (Backlog).

## Stolperfallen (gelernt)

- **DNS-Rewrite** `logger.dyness.com` → HA .126 im AdGuard; FritzBox beantwortet aus eigenem Cache mit echten NLB-IPs → Direkt-Query an .126:53 prüfen; FritzBox-Neustart leert Cache.
- **Nur EIN Server** für die Box (HA-Integration ODER MM-Relay, nie beide).
- **Megawatt-Anzeige:** int32 wird unsigned geparst — Plausibilitätsfilter (150–800 W) in sensor.py ist der Schutz; bei negativen Werten NICHT den Filter schwächen, sondern Semantik prüfen.
- **REST-Register-Sampling verliert kleine Frames** (Attribut zeigt nur den letzten Frame; 1082/1088er überdecken alles, SOC-Frames alle ~4-5 min kurz sichtbar) — frame_stats im HA-Prozess ist die WAHRHEITSQUELLE, nicht REST-Polling.
- **Test-Hygiene:** erst Ist-Wert-identischer Write, nie <150 W, kurze Fenster, Worklog nach jedem Test. User-Konsens für Modus-/DOD-Tests (einmaliges Schema freigegeben).
- Wetter: PV-Einstrahlung schwankt sekündlich (diffus↔voll) — Leistungs-Absolutwerte nie als feste Erwartung; nur Register-Diffs und Tasmota-Grob-Signale verwenden.
- **Versionsstrategie (User-Wunsch):** bewiesene Funktionalität = Major. Nächstes Feature-Release → Version +1.0-Schritt, nicht 0.1.x.

## Nach dieser Session (Backlog, User-Wünsche)

### UI-Überholung (User-Review 2026-11-01, nächster Major v1.1.0 — NUR Doku, nichts umgesetzt)
- **Ausgangs-Gauge-Skala falsch:** zeigt 0–50 MW statt 0–800 W (HQ-YAML hat min 0 max 800 — Ursache klären, evtl. HA-Rendering/Cache; ggf. Skala −800…+800 als Bilanz diskutieren: negativ = Abgabe ans Haus, positiv = Laden).
- **Steuerung-Kachel: roter „configuration error“** unter dem Dropdown (Ursache klären; sehr wahrscheinlich `type: slider` in der entities-Karte oder Select-Schema).
- **Dropdown + Buttons redundant → nur Buttons, aber aktiver Modus FARBLICH markiert** (User-Wunsch: das aktive „Lastpriorität“ leuchtet z. B. grün). Umzusetzen: Buttons mit `show_state`/Style oder `conditional`-Karten je Modus; Select-Entity kann bleiben (für Automations), nur nicht als Steuer-Element zeigen.
- **DOD-Button wirkt „funktionslos“** (kein Read-back, set_dod hat nur die 91-78-Quittung — ggf. Quittungs-Feedback anzeigen oder auf Box-Bestätigung verweisen).
- **Sensor-Verzögerung sichtbar machen:** Ausgang/SOC/Strom aktualisieren nur mit dem 4–5-min-Telemetrie-Takt; im UI „zuletzt aktualisiert“ anzeigen (Messwerte ≠ Steuerung, die sofort quittiert wird).
- **„(experimentell)“-Suffix entfernen** (SOC/SOH/Spannung/Strom sind validiert): Umbenennen → Entity-ID-Bruch → Dashboard + Automationen MIGRIEREN (IDs `sensor.balkon_…_soc` etc.), erst im selben Release wie Dashboard.

### Ideen geprüft — Entscheidungen
- **Box-Bypass bei Schwachlicht (<100 W PV direkt ins Haus): abgelehnt.** Architektur PV → Junior Box (MPPT+Akku) → Mikro-WR → Haus kennt KEINEN Software-Bypass (kein Protokoll-Befehl; Datenblatt: keine Nulleinspeisung). Hardware-Umschaltung (PV direkt an Mikro-WR) wäre nötig, aber: DC-Schalter unter Last = Lichtbogengefahr; Mikro-WR bei <100 W nur ~85–90 % Wirkung; Ersparnis <1 kWh/Jahr. Kein Nachverfolgen nötig, außer User fragt erneut.

### 🟥 P1 MORGEN: „Aus (Shutdown)" wirkungslos — Nacht-Chronologie belegt (2026-11-01/02)
- **Belegt (HA-History):** 17:41 „Aus (Shutdown)" gesetzt → Ausgang lief 17:42–19:57+ unverändert ~130 W (150er-Limit), kein Bruch. Um 20:43 wurde von Batterieprio übernommen (Lastdeckung). **Der Mode-255-Write änderte die Abgabe nicht** (Box hat ihn vermutlich dennoch gequittet — Kanal war den ganzen Tag gesund; ACK-Status des 255er-Writes nicht mehr rekonstruierbar, box_bestaetigung zeigt nur den letzten).
- **Morgen-Test (klar definiert):** 1) Ist-Zustand dokumentieren (Batterieprio/179 W, SOC ~20+ %). 2) Service `set_workmode` mode=255, power=150. 3) `box_bestaetigung` prüfen (ACK?) + Tasmota alle ~5 min über 30+ min. 4) Weiterhin 130 W → 255 ist im Schedule-Kontext wirkungslos ODER Frame für 255 falsch gebaut (power-Feld bei Shutdown? `ff`-mode byte prüfen, evtl. anderes power/Format — laut 31.10.-Notiz produzierte ein 255-Test damals 0,4 W, also KANN er wirken — Differenz herausfinden). 5) Rückstellung auf Batterieprio/179 W (Ist-Werte!).
- **Nutzer-Anforderung dahinter:** „nachts nichts ans Haus abgeben / Akku schonen" ist offenbar ein Kernwunsch (2. Nacht in Folge entlädt die Box). Wenn mode 255 nicht zuverlässig greift, ist das der wichtigste offene Punkt überhaupt.

### P2: Entlade-Stopp bei ~19-20 % über Nacht (2026-11-01/02, 22:12)
- Box stellte die Entladung bei SOC 19 % ein (Historie: 79→19 % 16:00–22:12, dann Stopp, morgens 20 %). DOD 95 erlaubt 5 %; 31.10. lief sie auf 13 % (andere Last/PV-Situation). Kein DOD-Versagen, aber ungeklärte Grenze — BMS-Spannungsschwelle unter Last? Lastabhängig? → bei Gelegenheit prüfen (konstante Last + SOC-Verlauf dokumentieren; ggf. BMS-Register-Sicht).

### 0x17D4-Sub-Typen — Ausgangsleistung nicht durchgängig stabil (NEU 2026-11-01 17:01)
- Box meldete im 1082B/115r-Frame **281 W**, Tasmota real **167 W** (Batterieprio+Dunkelheit, Batterie deckt Last −19,2 A — der 167-W-Wert ist korrekt und plausibel!). frame_stats zeigt ZWEI 1082er-Varianten: 115r (power_out=281, count=78) + 116r (power_out=0, count=1) — Raster-Rutsch (Parser-Bug beim Stur-Lesen; i+=1 bei unbekanntem Tag → eine Byte-Verschiebung erzeugt 116r und verfälscht Werte). **Offen:** Parser-Trennung nach echtem Frame-Layout (nicht Registrier-Zählen!) oder power_out-Referenz gegen Tasmota/Energiebilanz; bis dahin 0x17D4-Anzeige mit Vorsicht interpretieren (Tasmota ist der Zeuge). Auch der Gauge im Dashboard zeigt dann den falschen Wert — User-Sichtcheck nötig.

### Alt-Backlog
- nocode-Automations-GUI (Watchdog/Regeln im UI statt YAML).
- Veröffentlichungs-Redaktion: Default-Login `solarhub…` + Geräte-S/N in `tools/real_server_probe.py`/`ctl_150.hex` — User entscheidet.
- Langfristig: statische Server-IP der Box bei Inbetriebnahme (DNS-Regel überflüssig); evtl. Anker-Solix-Muster als Publikations-Vorbild.