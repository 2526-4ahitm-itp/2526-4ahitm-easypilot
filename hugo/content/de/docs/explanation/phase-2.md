---
title: "Phase 2: Simulation statt Steuerung"
weight: 2
---

## Änderung der Aufgabenstellung

| Datum | Änderung | Grund |
|---|---|---|
| 14.09.2026 | Phase 1 „Drohnensteuerung“ → Phase 2 „Drohnensimulation mit Physik-Engine“ | Die **DJI O4 Air Unit ist defekt**. Ohne sie gibt es kein Videobild und keine Steuerung über Brille und Fernbedienung, Tests mit der echten Drohne sind nicht mehr möglich. |

Details zum Defekt: [Bericht Air Unit](../../../project/reports/air-unit-defekt).

## Was Phase 2 liefern soll

Flugverhalten, Steuerung und Assistenzfunktionen sollen ohne Hardware entwickelt, getestet
und vorgeführt werden können (Pflichtenheft §1.2, §10.2). Vorführbares Ziel ist der Tag der
offenen Tür: Schüler:innen fliegen gegen ein Programm, das die Strecke allein fliegt (§20).

## Was wir gemacht haben (Stand 24.11.2026)

### Liftoff-Hover (Prototyp, fertig)

[Liftoff](https://www.liftoff-game.com/) ist ein FPV-Simulator mit einer realistischen
Physik-Engine (500 Hz). Er kann Position und Lage der Drohne per UDP ausgeben. Unser Python-Skript
`simulator/liftoff-hover` sitzt zwischen Funk-Controller und Liftoff:
- Im Normalbetrieb reicht es die Sticks durch.
- Auf Knopfdruck fliegt es selbst: abbremsen, dann Position, Höhe und Heading halten, wie bei
  einer DJI-Drohne mit GPS.

Wie der Regler funktioniert, steht unter [Hover-Regler](../hover-regler).

### Autonomes Rennen in Liftoff

Das Programm fliegt Liftoff-Rennstrecken allein und so schnell wie möglich (Pflichtenheft §20):
- **Rennsieg (18.10.2026):** „01 – Field Day“ in 3 Runden 59,2 s, bester Liftoff-Bot 1:33,7.
- **Alle Strecken:** Tore, Level, Gelände und Bäume kommen aus Liftoffs Spieldateien. In der
  Testreihe 9 schafft der Autopilot 53 von 90 offiziellen Rennen, gewertet von Liftoff selbst
  (Testreihe 7: 24 von 92).
- **KI-Torerkennung:** Ein selbst trainiertes Modell findet die Tore im Kamerabild und korrigiert
  falsch eingetragene Tore im Flug.
- **Ausweichen und ruhiger Flug:** Die Rennlinie weicht Hindernissen per „elastischem Band“ aus,
  die Ruckler sind von 53 auf 6 Richtungswechsel pro Minute gesunken.

Details: [Autonomes Rennen](../autonomes-rennen), [Testbericht](../../../project/reports/autonomes-rennen-test).

### GPS-Zielflug in Liftoff

Ziel als GPS-Koordinate oder relativ eingeben, die Drohne fliegt 1–3 m über dem Boden und weicht
Hindernissen aus der Streckendatei und aus dem Kamerabild aus (`goto.py`). Im eigenen Modell:
10 von 10 Zielen ohne Kollision. Die Testreihe in Liftoff für Meilenstein M12 ist noch offen.

### EasyPilot Studio und TDOT-Challenge

Die Oberfläche für den Tag der offenen Tür: Mensch gegen Autopilot.
- 5 Bot-Stufen von „Einsteiger“ (25 %) bis „Maschine“ (100 %), gleiche Zeitmessung für beide
- Splitscreen: neben dem Menschen läuft die Bestzeit des Autopiloten mit
- Bestenliste, Streckenwahl aus allen Rennen, Startampel, Bedienung vom Handy
- Live-Debug-Ansicht: erkannte Tore, geplante Linie, Tempo und Sticks

### Autopilot und Studio auf macOS

Autopilot und Studio laufen auch auf einem Mac mit Liftoff aus Steam. Statt vJoy steuert ein
virtuelles Gamepad über OpenJoystickDriver Liftoff, gestartet wird per Doppelklick.
Anleitung: `simulator/mac/README.md`.

### Eigener Freiflug-Simulator

Ein eigener FPV-Simulator ohne Liftoff (`simulator/autopilot/freefly`), damit wir die Physik
selbst in der Hand haben:
- **Welt:** ein Dorf mit Häusern, Bäumen und Hindernissen, fünf Strecken von „Anfänger“ bis „Profi“
- **Physik:** drei Modelle: „Klassisch“, „Liftoff-nah“ (aus über 200 000 Zeilen Liftoff-Telemetrie
  gefittet) und „Realistisch“ (echte 5-Zoll-Drohne mit Motoren, Betaflight-Regler, Akku und Wind)
- **Autopiloten:** dieselbe Rennlinie und derselbe Renn-Regler wie in Liftoff, auch nur nach
  Kamerabild, dazu ein neuronales Netz, das aus seinen eigenen Flügen weiterlernt
- **Für Besucher:innen:** Rennen gegen den Geist der Bestzeit, Ringe sammeln, Paket ausliefern,
  Freestyle, FPV-Look „Digital“ und „Analog“
- **Studio:** Das Studio steuert den eigenen Simulator als zweite Wahl neben Liftoff.

Starten (nach `simulator/mac/setup.sh`): `simulator/mac/Sim-Fliegen.command`, im Fenster mit
`--window`. Ohne Fernsteuerung wird mit der Tastatur geflogen.

### Web-Simulator (begonnen, ruht)

Geplant war ein Simulator im Browser auf Basis des 3D-Viewers in `webinterface/frontend`.
Der [Change `2026-10-13-phase2-web-simulator`](https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot/tree/main/openspec/changes/2026-10-13-phase2-web-simulator)
ruht seit 13.10.2026; die Arbeit ist in Liftoff und den eigenen Freiflug-Simulator gegangen.

## Was in Phase 2 noch offen ist

- **M9:** 10 Runden hintereinander bei 100 % ohne Fehler
- **M12:** Testreihe in Liftoff mit 10 GPS-Zielen, 0 Kollisionen
- Generalprobe mit Mitschüler:innen und Checkliste für den Tag der offenen Tür
- Review und Windows-Test für macOS-Port und Freiflug-Simulator (PR #84)
- Entscheidung, wie es mit dem Web-Simulator weitergeht

Plan und Tasks:
[`openspec/changes/2026-10-14-tdot-autonomes-rennen`](https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot/tree/main/openspec/changes/2026-10-14-tdot-autonomes-rennen),
das Pflichtenheft in §20.

## Phase 3

Noch nicht festgelegt. Was nach Phase 2 kommt, wird im Team und mit Betreuer:in besprochen.

## Was aus Phase 1 bleibt

Firmware, iOS-App (inklusive ihres eigenen Simulators) und Relay sind fertig und bleiben Teil des
Projekts. Sobald die Air Unit ersetzt ist, sind sie sofort wieder nutzbar.

## Offene Entscheidungen

- Web-Simulator: weiterführen (Physik-Engine: eigener Integrator oder Rapier / cannon-es) oder
  durch den eigenen Freiflug-Simulator ersetzen
- Speichert das Backend etwas für den Simulator (Bestzeiten, Aufzeichnungen)?
- Restliche Termine und Meilensteine von Phase 2
