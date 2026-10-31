# HA-Dashboard für die Dyness Junior Box

Die Integration liefert **Entitäten** (Messwerte) und **Services** (Befehle),
aber keine fertige Oberfläche — Dashboards („Lovelace“) baut HA immer selbst.
Diese Anleitung richtet das mitgelieferte `docs/dashboard.yaml` ein.

## Kurz erklärt

- **Entität** = ein einzelner Wert im System, z. B. der Sensor „Verbindung“.
- **Service** = ein Befehl, den man aufruft (hier: `set_workmode`, `set_dod`).
  Buttons im Dashboard sind nur hübsche Verpackungen für solche Befehle.
- **Dashboard** = die Seite(n), die du in HA siehst („Übersicht“ ist eines).

## Weg 1 (einfach): Roh-Editor

1. HA → **Einstellungen → Dashboards → Neu erstellen** → Name „Dyness“, ok.
2. Das neue Dashboard öffnen → Stift (Bearbeiten) → oben rechts **„⋮“ →
   Roh-Editor** (Raw configuration editor).
3. Inhalt von `docs/dashboard.yaml` **nach** den Zeilen mit `title:`/`views:`
   einfügen — genauer: die drei Karten-Blöcke (ab `- type: entities` bis zum
   Ende). Die `title:`/`views:`-Zeilen sind für den Datei-Modus (Weg 2) gedacht;
   im Roh-Editor wird nur der Karten-Teil übernommen.
4. Speichern. Fertig.

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

Im Code sind die IDs aus der S/N abgeleitet:

| Anzeige            | Entität (beispielhaft)                                        |
|--------------------|----------------------------------------------------------------|
| Verbindung         | `binary_sensor.dyness_junior_R07E8546681A0121_connection` (klein) |
| Akku (SOC)         | `sensor.dyness_junior_R07E8546681A0121_soc`                    |
| Firmware           | `sensor.dyness_junior_R07E8546681A0121_firmware`               |

Falls HA andere IDs vergeben hat: **Einstellungen → Geräte & Dienste →
Entitäten** → Suche „dyness“ → IDs aus der Tabelle übernehmen und im YAML
anpassen.

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