---
title: Flugmodi und Sicherheit
weight: 4
---

## Flugmodi der Companion-Firmware

| Modus | Wofür | Wer regelt |
|---|---|---|
| IDLE | Grundzustand, Motoren aus | niemand |
| BALANCE | Drohne auf dem Prüfstand waagrecht halten | P-Regler auf dem ESP32 um `baseThrottle` |
| MANUAL | Werte aus der App direkt übernehmen (Tests, Visualisierung) | die App |
| SOUND | Alle vier Motoren nach Handy-Neigung, für Akustik-Demos | die App über `TILT_SOUND` |
| RC | Echte Drohne mit den Simulator-Joysticks fliegen (LIVE) | P-Regler mit Soll-Winkeln aus `RC` |

Motorbelegung: M1 vorne links, M2 vorne rechts, M3 hinten links, M4 hinten rechts. Der
P-Regler rechnet `rAdj = kPRoll · (0 − roll)` und `pAdj = kPPitch · (0 − pitch)`. Beide Werte
werden je nach Motorposition addiert oder abgezogen und auf 1000–2000 begrenzt.

## Sicherheitsprinzip: Motoren aus, sobald etwas unklar ist

Eine Drohne mit 4S-Akku kann schwer verletzen. Deshalb gilt überall: Im Zweifel gehen die
Motoren auf 1000.

| Auslöser | Reaktion |
|---|---|
| Neustart | nicht scharf, alle Motoren 1000 |
| `START_*` ohne `ARM` | wird ignoriert |
| App trennt sich in SOUND oder RC | Motoren aus, IDLE |
| 1 s kein `TILT_SOUND` | Motoren 1000 |
| 500 ms kein `RC` | Motoren aus, IDLE |
| Handy-Neigung > 60° im Sound Mode | App beendet den Sound Mode |
| 2 s keine MSP-Antwort | `fc=false`, simulierte Telemetrie nur wenn nicht scharf |
| Standalone-Firmware: 1,5 s kein Heartbeat / Lage > 60° | FAILSAFE / CRASH, Motoren aus |

Die Specs dazu: `flight-modes` und `safety-failsafe` in der [Spec-Übersicht](../../reference/openspec).

## Zugangsdaten

WLAN- und OTA-Passwörter stehen nie im Repository. `secrets.ini.example` und
`wifi_secrets.example.h` zeigen das Format, die echten Dateien sind in `.gitignore`. Bis März 2026
lagen echte WLAN-Daten in einer Datei im Repo. Die Git-History wurde am 12.10.2026 bereinigt, die
Passwörter müssen trotzdem geändert werden.
