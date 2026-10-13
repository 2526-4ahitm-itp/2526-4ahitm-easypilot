---
title: Ursprüngliche Spezifikation
date: 2025-10-07
---

So war die iOS-App zu Projektstart gedacht. Die Notizen lagen bis 13.10.2026 als
`spezifikationen.txt`, `sprint_1.txt`, `sprint_2.txt` und `prompt.txt` im Root des Repositorys.
Sie sind hier zusammengefasst und dann gelöscht worden (in der Git-History bleiben sie erhalten).
Die gültigen Anforderungen stehen heute im Pflichtenheft `spec/fsd.md`.

## Idee

Eine iOS-App steuert und überwacht eine FPV-Drohne über WLAN. Die Drohne ist eine Nazgul DC5 ECO
mit Betaflight, darauf ein ESP32 als Brücke per UART und MSP. Gearbeitet werden sollte in
einwöchigen Sprints.

## Geplante Funktionen

| Bereich | Plan 2025 | Was daraus wurde |
|---|---|---|
| Dashboard | 3D-Modell, Gyro-Werte, Sensorstatus, Motor-% | umgesetzt (USDZ statt GLB) |
| Video-Livebild | offen, eher nicht | nicht umgesetzt; Air Unit inzwischen defekt |
| Simulator / Controller | experimentell, niedrige Priorität | Simulator-Tab mit Physik und LIVE-Modus (Sprint 4–5) |
| Konfiguration | „Härte“ der Drohne, Crash-Avoidance mit Abstandssensoren, Auto-Balancing | Algorithms-Tab mit Profilen; Crash-Avoidance nicht umgesetzt |
| Logs & Replay | Flughistorie, Blackbox-Daten, Replay im 3D-Modell | nicht umgesetzt; im Pflichtenheft unter „Kann“ |

## Erste Sprints

- **Sprint 1 (Plan):** Verbindung iPhone ↔ ESP32, Gyro live im Dashboard, Latenz unter 200 ms,
  Verbindungsstatus. Umgesetzt.
- **Sprint 2 (Plan):** echte MSP-Telemetrie (Lage, Akku) vom FC. Ging in Sprint 3 auf, Akku-Anzeige
  kam später.

## Offene Fragen von damals

- *Welcher Simulator?* Damals offen. Inzwischen gibt es den eigenen Simulator in der App, den
  Liftoff-Prototyp und den geplanten Web-Simulator.
- *WLAN-Protokoll?* Entschieden: WebSocket für Befehle und Telemetrie, UDP für die Discovery.
- *Stromversorgung des ESP32?* *vom Team zu ergänzen*.
