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

## Neues Ziel: Rennen am Tag der offenen Tür (in Arbeit)

Phase 2 hat ein vorführbares Ziel, das noch mit Betreuer:in abzustimmen ist:
- **Torbögen-Rennen in Liftoff:** Das Programm fliegt die Strecke allein und so schnell wie möglich.
- **Gegen Schüler:innen:** Am Tag der offenen Tür fliegen Schüler:innen dieselbe Strecke mit dem
  Controller, eine Bestenliste zeigt die Zeiten.
- **Zielflug:** Eine GPS-Koordinate eingeben, die Drohne fliegt 1–3 m über dem Boden ohne
  Kollision dorthin.

**Stand 18.10.2026:** Das Programm gewinnt das Liftoff-Rennen „01 – Field Day“ gegen alle
Liftoff-Bots (3 Runden 59,2 s, bester Bot 1:33,7). Die Torposen stammen aus Liftoffs
Streckendateien; ein selbst trainiertes KI-Modell erkennt die Tore im Kamerabild und korrigiert sie.
Der Zielflug ist im eigenen Modell getestet, in Liftoff noch offen. Details:
[Autonomes Rennen](../autonomes-rennen), [Testbericht](../../../project/reports/autonomes-rennen-test).

Plan in Phasen mit Go/No-Go-Punkten:
[`openspec/changes/2026-10-14-tdot-autonomes-rennen`](https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot/tree/main/openspec/changes/2026-10-14-tdot-autonomes-rennen),
das Pflichtenheft in §20.

## Was aus Phase 1 bleibt

Firmware, iOS-App (inklusive ihres eigenen Simulators) und Relay sind fertig und bleiben Teil des
Projekts. Sobald die Air Unit ersetzt ist, sind sie sofort wieder nutzbar.

## Offene Entscheidungen

- Physik-Engine: eigener Integrator (Vorschlag im Design) oder Bibliothek wie Rapier / cannon-es
- Speichert das Backend etwas für den Simulator (Bestzeiten, Aufzeichnungen)?
- Restliche Termine und Meilensteine von Phase 2
