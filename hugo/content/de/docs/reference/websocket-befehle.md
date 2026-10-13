---
title: WebSocket-Befehle
weight: 2
---

App → ESP32 über `ws://<esp32>:81`, ein TEXT-Frame pro Befehl. Zahlen immer mit Dezimalpunkt
und zwei Nachkommastellen (ArduinoJson kennt kein Komma). Das sichern die iOS-Tests
`DroneCommandTests` ab.

| Befehl | Felder | Wirkung | nur scharf |
|---|---|---|---|
| `{"cmd":"ARM"}` | – | scharf schalten | – |
| `{"cmd":"DISARM"}` | – | entschärfen, IDLE, Motoren aus | – |
| `{"cmd":"STOP"}` | – | IDLE, Motoren aus | – |
| `{"cmd":"START_BALANCE",…}` | `baseThrottle`, `kPRoll`, `kPPitch` | BALANCE | ja |
| `{"cmd":"START_MANUAL",…}` | `roll`, `pitch`, `yaw`, `m1`–`m4`, `voltage`, `batteryPercentage` | MANUAL | ja |
| `{"cmd":"START_SOUND","maxPWM":N}` | N wird auf 1000–1500 begrenzt | SOUND | ja |
| `{"cmd":"TILT_SOUND","pwm":N}` | N ≤ `maxPWM` | alle Motoren auf N, 1-s-Timeout neu | ja, nur in SOUND |
| `{"cmd":"START_RC",…}` | `kPRoll`, `kPPitch` | RC, Stick-Werte auf 0 | ja |
| `{"cmd":"RC",…}` | `thr` 1000–2000, `pit`/`rol` ±45°, `yaw` ±100 | Stick-Update, 500-ms-Timeout neu | ja, nur in RC |
| JSON ohne `cmd` | Telemetrie-Felder | überschreibt Lage/Motoren/Akku (MANUAL-Update) | – |
| `SAFE_TEST` (Text) | – | M1 = 1050 für 500 ms | ja |
| `SIMULATE` (Text) | – | simulierte Telemetrie wieder an (ohne FC, nicht scharf) | – |

## Beispiele

```json
{"cmd":"START_BALANCE","baseThrottle":1200,"kPRoll":10.00,"kPPitch":12.50}
{"cmd":"START_MANUAL","roll":1.50,"pitch":-2.00,"yaw":0.00,"m1":1000,"m2":1100,"m3":1200,"m4":1300,"voltage":16.80,"batteryPercentage":100}
{"cmd":"RC","thr":1350,"pit":5.00,"rol":-3.00,"yaw":0.00}
```

Spec: `command-protocol`.
