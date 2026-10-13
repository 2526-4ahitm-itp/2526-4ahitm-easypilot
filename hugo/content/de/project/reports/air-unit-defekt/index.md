---
title: Air-Unit-Defekt
date: 2026-09-14
---

## Was passiert ist

Die **DJI O4 Air Unit** der Drohne ist defekt. Die Air Unit ist Kamera, Videosender und
Funkempfänger in einem:
- Sie schickt das Bild an die DJI-Brille.
- Sie empfängt die Steuerbefehle der DJI-Fernbedienung und gibt sie an den Flight Controller weiter.

Ohne sie gibt es:
- kein Videobild,
- keine Steuerung über Brille und Fernbedienung,
- keine Flugtests mit der echten Drohne.

Wann und wie der Defekt aufgetreten ist und ob eine Reparatur oder ein Ersatz geplant ist:
*vom Team zu ergänzen*.

## Folgen für das Projekt

Am **14.09.2026** wurde die Aufgabenstellung geändert: von Phase 1 „Drohnensteuerung“ zu Phase 2
„Drohnensimulation mit Physik-Engine“ (siehe [Phase 2](../../../docs/explanation/phase-2)).

| Teil | Auswirkung |
|---|---|
| Firmware, iOS-App | funktionieren, aber nicht mehr im Flug testbar; LIVE-Modus nie im Flug erprobt |
| Telemetrie am Boden | geht weiter: Der ESP32 liest den Flight Controller auch ohne Air Unit |
| Neue Arbeit | Simulation: Liftoff-Hover-Prototyp (fertig), Web-Simulator (in Arbeit) |

In OpenSpec ist der Defekt als offene Anforderung festgehalten (`hardware-platform`,
„Working video and radio link“, `not-implemented`).
