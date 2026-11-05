# HA-Dashboard für die Dyness Junior Box

Die Integration liefert **Entitäten** (Messwerte) und **Services** (Befehle),
aber keine fertige Oberfläche — Dashboards („Lovelace“) baut HA immer selbst.
Diese Anleitung richtet das mitgelieferte `docs/dashboard.yaml` ein.

## Kurz erklärt

- **Entität** = ein einzelner Wert im System, z. B. der Sensor „Verbindung“.
- **Service** = ein Befehl, den man aufruft (hier: `set_workmode`, `set_dod`).
  Buttons im Dashboard sind nur hübsche Verpackungen für solche Befehle.
- **Dashboard** = die Seite(n), die du in HA siehst („Übersicht“ ist eines).

## Weg 0 (empfohlen): automatisch per Skript

Aus dem Repo heraus (Rechner im selben Netz wie HA, Python mit
`websockets` + `pyyaml`):

```bash
python3 tools/install_dashboard.py                 # legt/aktualisiert Dashboard 'dyness-junior-box'
python3 tools/install_dashboard.py --url http://<ha-ip>:80 --token <TOKEN>
```

Token wahlweise als `--token`, Env `HA_TOKEN` oder Datei `--token-file`
(Default `~/.hermes/creds/ha_token`) — nie durch den Chat. Das Skript
verbindet sich per WebSocket (HA ≥ 2024) und schreibt die Konfiguration aus
`docs/dashboard.yaml`; existiert das Dashboard nicht, wird es angelegt.

Hinweis: Die Entity-IDs in der Datei sind die des Autors (inkl. evtl.
Area-Präfix). Zeigt bei dir etwas „Nicht verfügbar“, die drei IDs unter
**Einstellungen → Geräte & Dienste → Entitäten → Suche „dyness“** nachsehen
und im Dashboard ersetzen.

## Weg 1 (einfach): Roh-Editor

1. HA → **Einstellungen → Dashboards → Neu erstellen** → Name „Dyness“, ok.
2. Das neue Dashboard öffnen → Stift (Bearbeiten) → oben rechts **„⋮“ →
   Roh-Editor** (Raw configuration editor).
4. Im Roh-Editor **alles löschen** (dort steht nur `[]` oder alte Karten) und
   den **kompletten Inhalt von `docs/dashboard-cards.yaml`** einfügen — diese
   Datei enthält NUR die Karten, ohne `title:`/`views:`-Kopf (der gehört in
   die Datei `docs/dashboard.yaml`, die nur für den yaml-Datei-Modus, Weg 2,
   gedacht ist).
5. Speichern. Fertig.

## Weg 2 (mit Datei, yaml-Modus)

1. Auf dem HAOS-Host `configuration.yaml` ergänzen:

   ```yaml
   lovelace:
     mode: yaml
   ```

   (bei HAOS z. B. über den Add-on „Advanced SSH & Web Terminal“ oder
   „Studio Code Server“; danach HA neu laden/starten)
2. `docs/dashboard.yaml` nach `/config/dashboards/dyness.yaml` kopieren und
   den Pfad in `configuration.yaml` registrieren:

   ```yaml
   lovelace:
     mode: yaml
     dashboards:
       dyness:
         mode: yaml
         filename: dashboards/dyness.yaml
   ```

3. HA neu laden. Dashboard „Dyness“ erscheint links.

## Entitäten-IDs prüfen

Wichtig: HA leitet die Entity-IDs aus den (deutschen) Namen ab, nicht aus
den unique_ids — inkl. eventuellem Area-Praefix (`balkon_`). Auf der
Referenz-Instanz (2026-10-31):

| Anzeige     | Entität (auf der Referenz-Instanz)                              |
|-------------|-----------------------------------------------------------------|
| Verbindung  | `binary_sensor.dyness_junior_box_r0000000000000000_verbindung`   |
| Modus       | `select.balkon_dyness_junior_box_r0000000000000000_modus`        |
| Leistung    | `number.balkon_dyness_junior_box_r0000000000000000_leistungsgrenze` |

SOC-/Firmware-Sensoren sind noch NICHT registriert (Sensor-Plattform —
folgt mit der Telemetrie-Dekodierung; offener Punkt). Falls eine Karte
„Nicht verfügbar“ zeigt: **Einstellungen → Geräte & Dienste → Entitäten →
Suche „dyness“** → echte ID uebernehmen.

## Was die Buttons tun

| Button                    | Befehl                               | Bedeutung |
|---------------------------|--------------------------------------|-----------|
| 150 / 200 / 300 / 500 W   | `set_workmode`, mode **16**          | **Lastpriorität**: Gesamt-Ausgang auf den Wert deckeln (Akku + PV füllen auf). |
| Batterie zuerst (800 W)   | `set_workmode`, mode **17**          | **Batteriepriorität**: Akku vorrangig entladen. |
| Entladetiefe 95 %         | `set_dod` mit 95                     | Akku darf bis 95 % Tiefe entladen werden (gemessen: lief nachts bis 13 % SOC). |

Sicherheit:
- **Mindestens 150 W** — alles darunter gilt der Box als „unbegrenzt“ und
  kann den Akku leerlaufen lassen. Der Service klemmt selbst auf 150 W.
- Werte wirken auf die **Gesamt-Ausgangsleistung**; die Tasmota
  (192.168.178.119) zeigt ≈ Soll − 14 W Wandlungsverlust.
- Die Box hat **kein Read-back**: Welcher Modus gerade aktiv ist, steht
  nirgends. Sollwert selbst merken (oder in eine HA-Notiz kopieren).

## Steuern ohne Dashboard (manuell, aktuelles HA-UI)

Zum Ausprobieren braucht es kein Dashboard — der Befehl geht auch direkt:

1. **Einstellungen → System → Tools** (in älteren HA-Versionen hieß der Ort
   „Entwickler-Tools“; falls er in der Seitenleiste fehlt: eigenes Profil →
   „Erweiterter Modus“ einschalten).
2. Reiter **„Actions“** (ältere Versionen: „Dienste“) — **nicht den Reiter
   „Events“!** Events sind Durchsagen an alle, kein Befehl an die Box.
3. Dienst `dyness_junior.set_workmode` wählen. Ab **v0.1.2** zeigt HA dafür
   Felder an:
   - **mode** (Dropdown): `16` Lastpriorität, `17` Batteriepriorität, `255` Shutdown
   - **power** (Zahlenfeld): **150–800** — alles darunter lehnt HA mit
     Fehlermeldung ab (Akku-Gefahr!)
   - `set_dod`: einziges Feld **dod**, 0–100 (z. B. 95)
4. „Aktion ausführen“ → Ergebnis im HA-Log (Einstellungen → System →
   Protokolle): *„set_workmode … gesendet“* oder *„nicht gesendet (Box
   offline?)“*.

YAML-Modus (falls gewünscht) — wichtig, in **Block-Schreibweise**:

```yaml
service: dyness_junior.set_workmode
data:
  mode: 16
  power: 200
```

⚠️ **Komma-Falle:** Die Kurzschreibweise `data: {mode:16 power:200}` ist
ungültiges YAML (fehlendes Komma) — HA liest daraus einen einzigen kaputten
Eintrag und der Dienst lehnt ab. Immer Block-Schreibweise verwenden.

## Verbindung prüfen (wenn „Verbindung“ aus ist)

1. **AdGuard → Query Log:** `logger.dyness.com` muss auf die HA-IP (.126)
   zeigen. Die Box verbindet sich alle ~14 s neu — der Log-Ausgang ist der
   Live-Beweis, dass sie anklopft (Quelle 192.168.178.69).
2. **Box Power-Cycle:** ~10 s Strom weg. Das triggert sofort einen neuen
   Verbindungsversuch (nach vielen Fehlversuchen geht die Box in Backoff).
3. **`homeassistant.log`** (Einstellungen → System → Protokolle): nach
   „Dylink-Server lauscht“ bzw. „set_workmode … gesendet“ suchen.

Der echte Kontroll-Beweis ist ein **identischer Schreibtest**: Button „150 W“
mit dem aktuell aktiven Wert drücken → Log zeigt „gesendet“; dann kurz 200 W
→ Tasmota sollte ~186 W zeigen → zurück auf 150 W. Nie <150 W testen.