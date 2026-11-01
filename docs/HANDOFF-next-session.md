# Handoff — nächste Session: Dashboard-Aufräumen + Temperatur-Sensoren

Stand 2026-11-01 MITTAG — **v1.0.0 (Major!): Steuerung + Monitoring sind als bewiesen markiert.** Alle Sensoren live, Steuerung ent-cloudt (00-78 → Tasmota-Verifikation), Frame-Typen getrennt. **Heutige Durchbrüche:** (1) **Frame-Längen-Schlüssel:** echte Telemetrie-Frames sind 1082 B (115 Register: SOC/SOH/Spannung/Strom/0x17D4-Ausgang/CAPACITY…) und 1088 B (123 Register: Zellspannungen, SOC-Duplikate 0x36B0/0x3520, Temperaturen, 0x4588 128↔64). (2) **0x1770 enttarnt — KEIN Sollwert:** Bilanz-/Netto-Leistung, springt −244…+18 W bei FESTEM Soll 150/200 W (Wert folgt Writes NICHT); Plausibilitäts-Filter (150–800) schluckt den Megawatt-Unsinn (User-Befund „5-MW-Skala" = −169 W unsigned gelesen). (3) **Modus-Read-back nicht in der Telemetrie:** 0x1900 blieb bei Mode-17-Test 16 (4×1082er-Sichtungen); sichtbarer Modus-Unterschied ist real (Tasmota 134→323 W bei Mode 17/Last-Deckung→0,4 W), aber KEIN Register meldet ihn. → **v1.0.0-Ansatz: 91-78-ACK der Box = der einzige nachweisbare Read-back** (Attribut `box_bestaetigung` an Modus+Leistungsgrenze; Config-Report 91 71 wird ab sofort auch als Register best-effort gescannt — letzter möglicher Ort). (4) 0x17D4 = Ausgangsleistung VERIFIZIERT (Tasmota 323↔336 W synchron). (5) Tasmota misst STABILEN Box-Ausgang (14 Messungen: 133,6–136,0 W), Netto-Schwankungen sind Wetter/PV-bedingt (Batterie puffert; current +19 A…−1,6 A).

**Nächste Goals: (1) Dashboard-Karten** (SOC/Ausgangsleistung/Spannung ins docs/dashboard.yaml + install_dashboard.py, User-Wunsch ausstehend), **(2) Temperatur-Sensoren** (0x1AF4/0x1B58 + 0x47E0/0x48A8/0x4A38/0x4B00 = 65,0 konstant, 0x4A9C=−20,0 — experimentell), (3) Config-Report-Register-Scan auswerten (steckt der Modus im 475er?), (4) nocode-GUI (Backlog).

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
3. **frame_stats lesen** (SOC-Entity-Attribut, REST): Config-Report (`~475B/?r`) — wenn der jetzt als `X B/r` in der Statistik auftaucht, prüfen: trägt er 0x1900/0x1770/Modus-Werte? Das ist der letzte ausstehende Modus-Kandidat.
4. **Dashboard-Aufräumen (User-Wunsch):** `docs/dashboard.yaml` + `docs/dashboard-cards.yaml` pflegen (SOC-/Ausgangsleistungs-/Spannungs-Karten), `tools/install_dashboard.py` ausführen, Entity-IDs gegen `/api/states` abgleichen (nie raten!).
5. **Temperatur-Sensoren:** 0x1AF4/0x1B58 (Telemetrie?) + großes 1088er-Raster (0x47E0/0x48A8/0x4A38/0x4B00 = 65,0; 0x4A9C = −20,0) — Werte über Zeit gegen SOC/Strom korrelieren; dann Sensoren in sensor.py.
6. **Falls Zeit:** nocode-Automations-GUI (Backlog).

## Stolperfallen (gelernt)

- **DNS-Rewrite** `logger.dyness.com` → HA .126 im AdGuard; FritzBox beantwortet aus eigenem Cache mit echten NLB-IPs → Direkt-Query an .126:53 prüfen; FritzBox-Neustart leert Cache.
- **Nur EIN Server** für die Box (HA-Integration ODER MM-Relay, nie beide).
- **Megawatt-Anzeige:** int32 wird unsigned geparst — Plausibilitätsfilter (150–800 W) in sensor.py ist der Schutz; bei negativen Werten NICHT den Filter schwächen, sondern Semantik prüfen.
- **REST-Register-Sampling verliert kleine Frames** (Attribut zeigt nur den letzten Frame; 1082/1088er überdecken alles, SOC-Frames alle ~4-5 min kurz sichtbar) — frame_stats im HA-Prozess ist die WAHRHEITSQUELLE, nicht REST-Polling.
- **Test-Hygiene:** erst Ist-Wert-identischer Write, nie <150 W, kurze Fenster, Worklog nach jedem Test. User-Konsens für Modus-/DOD-Tests (einmaliges Schema freigegeben).
- Wetter: PV-Einstrahlung schwankt sekündlich (diffus↔voll) — Leistungs-Absolutwerte nie als feste Erwartung; nur Register-Diffs und Tasmota-Grob-Signale verwenden.
- **Versionsstrategie (User-Wunsch):** bewiesene Funktionalität = Major. Nächstes Feature-Release → Version +1.0-Schritt, nicht 0.1.x.

## Nach dieser Session (Backlog, User-Wünsche)

- nocode-Automations-GUI (Watchdog/Regeln im UI statt YAML).
- Veröffentlichungs-Redaktion: Default-Login `solarhub…` + Geräte-S/N in `tools/real_server_probe.py`/`ctl_150.hex` — User entscheidet.
- Langfristig: statische Server-IP der Box bei Inbetriebnahme (DNS-Regel überflüssig); evtl. Anker-Solix-Muster als Publikations-Vorbild.