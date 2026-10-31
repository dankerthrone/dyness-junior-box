# Handoff — nächste Session: HAOS-Test der Integration v0.1

Geschrieben 2026-10-31 (Session-Ende; NATRAG zweite Hälfte). **Ziel der NÄCHSTEN Session: SOC-/Telemetrie-Dekodierung + echte Zustands-Entities.** Der HAOS-Test ist DURCH (v0.1.3 steuert die Box nachweislich — Tasmota 133 W bei 150-W-Write), aber Slider/Dropdown zeigen nur „zuletzt gesetzt“, nicht den echten Box-Zustand — User fordert zu Recht echtes Read-back. Einzige Quelle dafür: die periodischen Telemetrie-Register (SOC-Heuristik `0x04b0` eichen, prüfen ob aktueller Modus/Leistung in den Frames stecken) + 9002-Klartext-Pfad. Danach: Real-State in Number/Select-Entities + SOC-GUI. nocode-Automations-GUI bleibt Backlog.

## Wo steht was (Gedächtnis der Maschine)

| Ort | Inhalt |
|---|---|
| `~/dyness-junior-box/` | Repo `dankerthrone/dyness-junior-box` (public). Integration in `custom_components/dyness_junior/`, Protokoll-Lib in `dylink/`, Doku in `docs/` (ROADMAP, DNS-MITM, APK-Analyse), Werkzeuge in `tools/` |
| `~/dyness-probe/` | lokale Probe-Werkzeuge + Mitschnitte: `dyness_probe.py` (Cloud-API, Creds in `config.json` — **nie durch den Chat**), `relay_5005_full.log` (Roh-Captures, NICHT im Repo), `ctl_150.hex` (Quelle der generierten Frames), `dylink_server_v*.py` (Fake-Server-Entwicklung) |
| `~/WORKLOG.md` + Joplin-Notiz `9dc077a80f4a48fa87a28c89c64b8824` | kompletter Tageslauf |
| Skill `dyness-junior-box` | Protokoll-Referenz (Dylink, 00-78, Register, IPs) — **beim Session-Start laden** |
| MM = 192.168.178.146 | Raspi 3B+; darauf läuft noch das TCP-Relay (Port 5005+1883 → echte Cloud) als Hintergrundprozess — beim HAOS-Test **stoppen**, damit nur HA die Box bedient |

## Wahrheitstabelle (Stand 10:50 — alles an echter Hardware gemessen)

- Box = Client auf `logger.dyness.com:5005` (Dylink, 4-Byte-Längen-Frames, ~14-s-Reconnect). **MQTT/1883 ist ein TOTPFAD.** Live-Daten gehen zusätzlich an `cloud.raymoniot.com:9002` (HTTP, plaintext) — MITM-Ziel für später.
- Login: `10 <SN> 91 00 solarhub solarhub@123456` (Default-Creds im Gerät) → Server: Banner + `10 <SN> 91 00 01`.
- Bind `10 <SN> 91 22` → BindACK `…91 22 00 00 01 a1 91 <3B-Token>` + Zeitsync `00 77 …`; Box quittiert `91 87 …`.
- Config-Report `91 71` (~475 B) → ACK `99 71 01`. Telemetrie (>100 B) → ACK `99 04 01`.
- **Steuerbefehl `00 78`:** SetWorkMode `20 d0 49 <mode> <p/8>` (mode 16→`10`, 17→`11`, 255→`ff`; p = W/8 gerundet, 150→`13`); SetBase-DOD `19 c8 49 <dod>` (dezimal-hex). Box bestätigt mit `10 <SN> 91 78 …`. **Bewiesen:** 200 W → 183 W an der Tasmota, 150 W → 138 W.
- **150 W ist harte Untergrenze** — darunter = „unbegrenzt" (Akku-Leerlauf!). Integration erzwingt 150 W als Minimum (s. `const.py`).
- DOD 95 greift nachweislich (Batterie lief nachts auf 13 %).
- Box-Power-Cycle = 10 s Strom weg; nach Reconnect ~1 min anliegen. Nach vielen Fehlversuchen geht die Box in Backoff (minutenlang) — Power-Cycle triggert sofort neu.

## Testplan nächste Session (Reihenfolge)

1. **Skill laden:** `skill_view(dyness-junior-box)` (wurde evtl. aus dem Kontext komprimiert).
2. **MM-Relay stoppen** (Port 5005/1883-Proxys auf .146 killen — PIDs per `ss -tlnp | grep -E ":5005|:1883"` ermitteln). Box läuft dann ins Leere → Backoff, egal.
3. **Integration auf HAOS bringen:** Auf dem Laptop: `git -C ~/dyness-junior-box push` (falls neue Commits); dann im HA-WebUI: HACS → Integrationen → ⋮ → Benutzerdefinierte Repositories → `https://github.com/dankerthrone/dyness-junior-box` (Kategorie **Integration**) → installieren → HA neu starten.
4. **Integration hinzufügen:** Geräte & Dienste → „Dyness Junior Box (Local)" → S/N `R07E8546681A0121`, Port 5005, Bind 0.0.0.0.
5. **DNS-Rewrite umbiegen:** AdGuard (Filter-Tab!) `logger.dyness.com` → **HA-IP** (statt .146). Box-Power-Cycle. Erwartung: HA-Logs (`homeassistant.log`, Stichwort `Dylink-Server lauscht`), Sensor „Verbindung" = an. Fehlerbilder: (a) Port 5005 belegt (ConfigEntryNotReady) — jemand anderes lauscht; (b) keine Verbindung → `nslookup logger.dyness.com` prüfen (muss HA-IP zeigen), Box-Power-Cycle wiederholen.
6. **Steuer-Test an echter Box (Vorsicht!):** Service `dyness_junior.set_workmode` mit identischem Ist-Wert (150 W / 16) testen → HA-Log „gesendet"; dann kurz 200 W, Tasmota (192.168.178.119, `Status 8`) sollte ~183 W zeigen; dann zurück auf 150 W. **Test-Hygiene: erst Ist-Wert-identischer Write, nie <150 W.**
7. **SOC-Ground-Truth:** Telemetrie-Register (Parser `0x04b0` = SOC-Heuristik) gegen Cloud-API (`~/dyness-probe/dyness_probe.py realtime`, ~5 min Toleranz) abgleichen → Heuristik bestätigen oder korrigieren (`parser.py`).
8. **Falls Zeit:** 9002-Capture (Rewrite `cloud.raymoniot.com` → Proxy → Mitschnitt) für den Rest-Datenpfad.

## Stolperfallen (gelernt)

- **DNS-Rewrite-Falle:** `logger.dyness.com` muss im AdGuard (und ggf. FritzBox-DNS) auf HA zeigen; solange sie auf .146 zeigt, erreicht die Box HA nicht, obwohl die Integration läuft.
- **Zwei Server = Verwirrung:** Nur EIN Server für die Box: entweder HA-Integration ODER MM-Relay, nie beide im Rewrite.
- **Relay-Timeline:** Solange das MM-Relay steht, ist die Box „in der Cloud" (App online). Nach Umstellung auf HA zeigt die App „offline" — gewollt.
- Port 5005 binden: HA-Integration läuft im HA-Prozess und darf binden (kein Root nötig); bei Fehler `Port belegt` → andere Dienste prüfen.
- Bei HAOS-Fehlern: `homeassistant.log` via HA-WebUI (Einstellungen → System → Protokolle) — kein SSH nötig.
- Commits: Repo-Identität ist `Timon <deine@email.de>` (Placeholder) — user-Entscheidung, ob auf GitHub-noreply umgestellt wird. Neues pushen: `git add -A && git commit && git push`.

## Zustand bei Session-Ende (zweite Hälfte, 2026-10-31) — komprimiert

- **Releases:** v0.1.0 (HACS-Install-Fix: Repo hatte KEINE Releases — HACS braucht Release/Tag!), v0.1.1 (S/N-Platzhalter aus Config-Flow entfernt), v0.1.2 (Service-Schemas → Felder in Tools→Actions), v0.1.3 (Select-Entity Modus + Number-Entity Leistungsgrenze/Slider). Releaseroutine: manifest-Version bumpen → push → `gh release create <v>`.
- **MM-Relay (.146) dauerhaft gestoppt** (tcp_proxy 5005/1883 gekillt, kein Autostart). DNS-Rewrite `logger.dyness.com` → HA .126. Steuer-Beweis: identischer 150-W-Write → Tasmota 133 W.
- **⛔ OFFENER BEFUND bei v0.1.3-UI-Test:** Tasmota 0.4 W, obwohl Cloud-API realtime **SOC 100 %** meldet (16.81 V, SOH 100) → Akku VOLL, trotzdem 0 W → Verdacht: Box steht im **Shutdown-Modus** (Mode-255-Test aus der UI?). Recovery: Modus auf Lastpriorität + 150 W; wenn weiter 0 W → Box-Power-Cycle (10 s Strom weg). Vor jeder SOC-Arbeit: Box-Zustand klären!
- **Ground-Truth-Anker:** SOC 100 % (2026-10-31 ~16:00, Cloud-API) zum Vergleich mit Telemetrie-Dekodierung notiert.
- **Real-State-Problem:** Cloud-API bietet kein Read-back (status→null); einzig mögliche Quelle für echten Modus/Leistung/SOC = Telemetrie-Register der Box → genau das ist das nächste Session-Ziel. User-Kritik: „Slider sollen echten Box-Zustand zeigen“ — angenommen und ins Ziel übernommen.

## Nach dieser Session (Backlog, User-Wünsche)

- nocode-Automations-GUI (neue Session, frischer Kopf) — Idee: Watchdog/Regeln im UI statt YAML.
- Veröffentlichungs-Redaktion: Default-Login `solarhub…` + Geräte-S/N liegen in `tools/real_server_probe.py`/`ctl_150.hex` — User entscheidet, ob redigiert.
- Langfristig: statische Server-IP der Box bei Inbetriebnahme (würde DNS-Regel überflüssig machen); evtl. Anker-Solix-Muster (Lib + Integration) als Publikations-Vorbild.