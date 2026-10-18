---
title: "Liftoff-Autopilot: Daten und Belegungen"
weight: 8
---

## Gemessenes Drohnenmodell (Armattan Mongoose, Liftoff 1.7.6)

| Größe | Wert | Quelle |
|---|---|---|
| Schwebegas | 0,281 | `sysid.py` |
| Schubkurve | a = k · Gas², k = 124 m/s² (12,7 g statisch; Spiel-Angabe 5,79 kg Schub bei 449 g) | Gas-Sprünge |
| Schubverlust | ~50 % bei 20 m/s Steiggeschwindigkeit | Gas-Sprünge |
| Luftwiderstand | 0,033 1/m (a = –c·|v|·v) | Störgrößenschätzung bei 27 m/s |
| Raten (alle Achsen) | Betaflight RC-Rate 0,87, Expo 0, Super-Rate 0,71 → max. 600 °/s | Stick-Sprünge gegen Gyro |
| Kamera | FOV 125° horizontal, Uptilt 42°, Restfehler 0,8 px | `calib_cam.py` |
| Telemetrie | 100 Hz, Eingabeverzögerung ~20 ms (VSync aus) | Logs |

Gespeichert in `simulator/autopilot/drone.json`.

## Liftoff-Telemetrie

`Timestamp, Position, Attitude, Gyro, Input, Velocity` = 18 Little-Endian-Floats an
`127.0.0.1:9001`. Weltachsen Unity: x rechts, y oben, z vorne (linkshändig), Quaternion x, y, z, w.
Gyro = (Pitch, Roll, Yaw) in °/s, Input = (Gas, Yaw, Pitch, Roll) in –1…1.

## vJoy-Belegung

| vJoy | Liftoff (Rewired-Aktion) |
|---|---|
| Achse X / Y / Z / RX | Roll / Pitch / Gas / Yaw (Kategorie Flight) |
| Achse RY / RZ | Menü horizontal / vertikal (Aktion 0 / 1) |
| Knopf 1 | Bestätigen (2) |
| Knopf 2 | Zurück (3) |
| Knopf 3 | Reset Drohne (8) |
| Knopf 4 | Pause (10) |
| Knopf 5 | Exit (37) |

Rewired-Element-IDs für unbekannte Controller: Achsen 0–31, Knöpfe ab 32. Kategorien der
Controller-Maps: 0 Default, 1 Menu, 2 Flight, 6 TrackEditor, 8 Walk, 9 Multiplayer,
10 Miscellaneous (immer aktiv), 11 Replay.

## Tortypen

| Item | Öffnung B × H | Mitte über Bezugspunkt |
|---|---|---|
| `AirgateBig240H300B*`, `AirgateBigLiftoff*` | 3,00 × 2,40 m | 1,20 m |
| `MultiGPFloatSquare10x10Frame01` | 2,6 × 2,3 m | 4,05 m (gemessen) |
| `MultiGPFloatSquare10x10Frame02` | 2,6 × 2,3 m | 6,45 m (gemessen) |
| `CheckpointBox{B}mX{H}m` | B × H (unsichtbar) | 0 (Mitte) |
| `CheckpointBoxFlexible*` | aus `scale` | 0 (Mitte) |
| `InflatableArch*` | ~3,0 × 2,5 m (geschätzt) | halbe Höhe |

Werte in `track.py`, zum Prüfen siehe `dataset.py preview`.

## Ergebnisse

Siehe [Testbericht autonomes Rennen](../../../project/reports/autonomes-rennen-test).
