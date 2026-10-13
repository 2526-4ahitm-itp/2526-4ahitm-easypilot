---
title: 2025-11-25 Sprintplanung Sprint 1
date: 2025-11-25
---

Zeit: 9:00 – 9:20 · Ort: virtuell (Meet)

## Teilnehmer:innen

- David Windischbauer
- Simon Eder

## User Story: Live-Telemetrie in 3D-Visualisierung

*Als Drohnenpilot möchte ich den Live-Zustand der Drohne mit den Live-Telemetriedaten in einem
3D-Modell auf einem Dashboard sehen können, um eine Grundlage für spätere Simulationen zu haben.*

### Definition of Done

- **Echtzeit-Aktualisierung (Motordrehzahl):** Wird die Motordrehzahl erhöht, sind die neuen Werte
  innerhalb von 20 ms am 3D-Modell sichtbar.
- **Datenintegration:** Alle relevanten Live-Telemetriedaten (Position, Orientierung,
  Geschwindigkeit, Akkuzustand) werden korrekt und vollständig an das Dashboard übertragen.
- **3D-Modell:** Das Modell spiegelt Roll-, Nick- und Gierwinkel in Echtzeit wider.
- **Export:** Die aufgezeichneten Telemetriedaten können für externe Simulationswerkzeuge
  exportiert werden.

---

| Wer | Was |
| --- | --- |
| David | Prototyp der Datenschnittstelle (MAVLink), Latenz messen |
| Simon, David | einfaches Frontend mit React Three Fiber und dem bestehenden 3D-Modell |
| Simon | Echtzeit-Übertragung Backend → Frontend über WebSockets |
| David | Live-Telemetrie ins 3D-Modell, Echtzeit-Aktualisierung prüfen |
