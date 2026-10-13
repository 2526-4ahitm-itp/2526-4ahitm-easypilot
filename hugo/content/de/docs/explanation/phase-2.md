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
und vorgeführt werden können (Pflichtenheft §1.2, §10.2). Dafür gibt es zwei Wege:

### Liftoff-Hover (Prototyp, fertig)

[Liftoff](https://www.liftoff-game.com/) ist ein FPV-Simulator mit einer realistischen
Physik-Engine (500 Hz). Er kann Position und Lage der Drohne per UDP ausgeben. Unser Python-Skript
`simulator/liftoff-hover` sitzt zwischen Funk-Controller und Liftoff:
- Im Normalbetrieb reicht es die Sticks durch.
- Auf Knopfdruck fliegt es selbst: abbremsen, dann Position, Höhe und Heading halten, wie bei
  einer DJI-Drohne mit GPS.

Damit sind die **Regelalgorithmen** fertig und gemessen, bevor der Web-Simulator existiert. Wie
der Regler funktioniert, steht unter [Hover-Regler](../hover-regler).

### Web-Simulator (Ziel, in Arbeit)

Der Web-Simulator soll im Browser aus der LeoCloud laufen, ohne Installation:
- **Physik:** Starrkörper mit vier Schubkräften, Schwerkraft, Widerstand und Boden, fester Zeitschritt.
- **Steuerung:** Tastatur und Gamepad.
- **Flugmodi:** Rate, Angle und Hover, aus Liftoff-Prototyp und iOS-Simulator portiert.
- **HUD** mit den wichtigsten Flugwerten.

Grundlage ist der bestehende 3D-Viewer in `webinterface/frontend`. Plan und Tasks:
[Change `2026-10-13-phase2-web-simulator`](https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot/tree/main/openspec/changes/2026-10-13-phase2-web-simulator).

## Was aus Phase 1 bleibt

Firmware, iOS-App (inklusive ihres eigenen Simulators) und Relay sind fertig und bleiben Teil des
Projekts. Sobald die Air Unit ersetzt ist, sind sie sofort wieder nutzbar.

## Offene Entscheidungen

- Physik-Engine: eigener Integrator (Vorschlag im Design) oder Bibliothek wie Rapier / cannon-es
- Speichert das Backend etwas für den Simulator (Bestzeiten, Aufzeichnungen)?
- Restliche Termine und Meilensteine von Phase 2
