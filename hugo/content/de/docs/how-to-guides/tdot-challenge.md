---
title: "TDOT-Challenge betreiben (Mensch gegen Autopilot)"
weight: 8
---

Ziel: Besucher:innen fliegen eine Runde in Liftoff und treten gegen den Autopiloten in fünf
Stufen an. Ein Dashboard zeigt Live-Zeit, Minikarte mit dem Autopiloten als „Geist“ und die
Bestenliste. Voraussetzung: [Autonomes Rennen einrichten](../autonomes-rennen-einrichten).

## Stufen

| Stufe | Name | Tempo des Autopiloten | Referenzzeit Field Day (1 Runde) |
|---|---|---|---|
| 1 | Einsteiger | 25 % | 54,4 s |
| 2 | Fortgeschritten | 40 % | 36,1 s |
| 3 | Profi | 60 % | 26,5 s |
| 4 | Champion | 80 % | 23,3 s |
| 5 | Maschine | 100 % | 21,3 s |

Die Referenzzeiten fliegt der Autopilot vor dem Event selbst (Bedienseite → „Autopilot-Referenzlauf“).
Gespeichert wird die beste Zeit je Stufe, samt Zwischenzeiten und Flugbahn für den Geist.

## Aufbau

1. **Liftoff:** Quick Play → Freeflight → Umgebung *Straw Bale* → Track *01 - Field Day* → Play.
   Liftoff im 1920×1080-Fenster auf dem Hauptbildschirm.
2. **Controller der Besucher:innen** (Fernsteuerung im USB-Joystick-Modus oder Gamepad) anstecken
   und einmal kalibrieren:
   ```bash
   cd simulator
   python -m autopilot.pilot calibrate     # Sticks nach Anweisung bewegen
   python -m autopilot.pilot test          # Kontrolle der Werte
   ```
   Liftoff bleibt auf vJoy eingestellt – das Programm leitet den Controller durch. So kann
   zwischen Mensch und Autopilot gewechselt werden, ohne im Liftoff-Menü umzustellen, und
   beim Countdown sind die Sticks gesperrt (fairer Start).
3. **Event-Programm starten:**
   ```bash
   python -m autopilot.tdot --key <geheim>
   ```
4. **Seiten öffnen** (auch von Handy oder zweitem PC im selben Netz, `<pc>` = IP des Liftoff-PCs):

   | Seite | Zweck |
   |---|---|
   | `http://<pc>:8765/` | Dashboard für Beamer/zweiten Bildschirm |
   | `http://<pc>:8765/overlay` | kompaktes Overlay (transparent, z. B. OBS-Browserquelle) |
   | `http://<pc>:8765/admin?key=<geheim>` | Bedienung: Warteschlange, Start, Abbruch, Löschen |

   Auf dem Liftoff-PC **nichts anklicken**, solange geflogen wird – Liftoff braucht den Fokus.
   Bedient wird am besten vom Handy aus.

## Ablauf eines Laufs

1. Bedienseite: Name und Stufe eintragen → *In die Warteschlange*.
2. Das Programm setzt die Drohne an den Start, zeigt 3-2-1 auf dem Dashboard, dann **GO**.
3. Gezählt wird jedes Tor der Strecke in Reihenfolge, nur durch die Öffnung. Die Zeit endet im Zieltor.
4. Nicht gewertet: Reset/Absturz, Zeitlimit (180 s), Abbruch über die Bedienseite oder **F9**.

Mensch und Autopilot werden **gleich** gemessen (gleicher Start, gleiche Torprüfung). Liftoffs
eigener Timer wird nicht verwendet. Ergebnisse liegen in `simulator/autopilot/runs/tdot/`.

## Ohne Durchleitung

Wenn der Controller direkt in Liftoff eingestellt ist: `python -m autopilot.tdot --direct`.
Dann startet die Zeit, sobald die Drohne nach einem Reset den Startplatz verlässt; Referenzläufe
des Autopiloten gehen in diesem Modus nicht (Liftoff hört dann nicht auf vJoy).

## Fehlerbilder

| Symptom | Abhilfe |
|---|---|
| „Reset kommt nicht an“ | Liftoff einmal anklicken (Fokus), Lauf neu einreihen |
| „Keine Telemetrie“ | Liftoff ist im Menü – Free Flight starten |
| „no controller connected“ | Controller anstecken, `python -m autopilot.pilot list` |
| Dashboard zeigt nichts | Firewall: Port 8765 für das lokale Netz freigeben |
