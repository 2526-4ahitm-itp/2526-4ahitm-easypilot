---
title: Telemetrie
weight: 3
---

ESP32 → alle verbundenen WebSocket-Clients, alle 100 ms (10 Hz).

```json
{"roll":0.0,"pitch":0.0,"yaw":0.0,
 "m1":1000,"m2":1000,"m3":1000,"m4":1000,
 "voltage":16.8,"batteryPercentage":100,
 "armed":false,"mode":"IDLE","fc":false}
```

| Feld | Typ | Einheit / Werte |
|---|---|---|
| `roll`, `pitch` | float | Grad (aus MSP in Zehntelgrad) |
| `yaw` | float | Grad |
| `m1`–`m4` | int | PWM 1000–2000; M1 vorne links, M2 vorne rechts, M3 hinten links, M4 hinten rechts |
| `voltage` | float | Volt, aus `MSP_ANALOG` |
| `batteryPercentage` | int | 0–100, linear zwischen 13,0 V und 16,8 V (4S) |
| `armed` | bool | scharf geschaltet |
| `mode` | string | `IDLE`, `BALANCE`, `MANUAL`, `SOUND`, `RC` |
| `fc` | bool | `true`, sobald der Flight Controller per MSP antwortet; `false` = simulierte Daten |

## Verhalten der App

- Pflicht sind nur `roll`, `pitch`, `yaw` (ältere Firmware schickt nur diese). Fehlen sie, wird
  der Frame verworfen.
- Unbekannte Felder werden ignoriert.
- Unbekannter `mode` → IDLE. Achtung: `RC` wird derzeit auch als IDLE angezeigt (bekannter Bug).
- Akku unter 14,0 V → rote Anzeige.

## Liftoff-Telemetrie (Phase 2)

Liftoff sendet per UDP an `127.0.0.1:9001` Little-Endian-Floats in der Reihenfolge von
`TelemetryConfiguration.json`. Unsere Konfiguration (seit 18.10.2026) hat 18 Floats:

| Index | Inhalt |
|---|---|
| 0 | Timestamp (s) |
| 1–3 | Position x, y (Höhe), z in m, Unity-Koordinaten |
| 4–7 | Lage als Quaternion x, y, z, w |
| 8–10 | Gyro (Pitch, Roll, Yaw) in °/s |
| 11–14 | Input (Gas, Yaw, Pitch, Roll) |
| 15–17 | Geschwindigkeit x, y, z in m/s |

`liftoff-hover` liest nur die ersten 15 Floats, der Autopilot liest das Format aus der
Konfigurationsdatei. Mit VSync aus kommen die Pakete gleichmäßig mit 100 Hz.

Spec: `telemetry-stream`, `liftoff-hover`, `gate-racing`.
