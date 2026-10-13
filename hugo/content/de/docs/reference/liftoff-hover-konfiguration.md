---
title: Liftoff-Hover-Konfiguration
weight: 7
---

`simulator/liftoff-hover/config.json` entsteht durch `hover.py calibrate`. Fehlende Schlüssel
nimmt das Skript aus den Standardwerten. Beim Beenden speichert es das gelernte Schwebegas zurück.

| Schlüssel | Standard | Bedeutung |
|---|---|---|
| `controller_name` | `""` | Namensfilter; leer = erster Controller, der nicht vJoy ist |
| `vjoy_device` | 1 | vJoy-Gerätenummer |
| `telemetry_port` | 9001 | UDP-Port der Liftoff-Telemetrie |
| `loop_hz` | 250 | Regeltakt |
| `axes.throttle` | – | `index`, `low`, `high` (Rohwerte bei 0 % und 100 %) |
| `axes.yaw/pitch/roll` | – | `index`, `center`, `full` (Rohwert bei Vollausschlag rechts/vor) |
| `toggle` | – | Hover-Knopf: `type` `button` oder `axis`, `index`, `threshold` |
| `flight_mode` | `acro` | `acro` oder `angle` (Modus in Liftoff) |
| `center_rate_dps` | 200 | Drehrate bei Vollausschlag nahe der Mitte (RC-Rate × 200) |
| `hover_throttle` | 0,30 | Schwebegas 0–1, wird im manuellen Flug nachgelernt |
| `blend_out_s` | 0,5 | Überblendung zurück zur Pilot:in |

## Regler (`gains`)

| Schlüssel | Standard | Einheit |
|---|---|---|
| `att_p` | 6,0 | (°/s) pro ° Lagefehler |
| `yaw_p` | 3,0 | (°/s) pro ° Heading-Fehler |
| `pos_p` | 1,2 | m/s² pro m |
| `pos_d` | 2,2 | m/s² pro m/s |
| `alt_p` | 1,5 | Soll-Steigrate (m/s) pro m Höhenfehler |
| `alt_d` | 3,0 | m/s² pro m/s Steigratenfehler |
| `alt_i` | 0,10 | Gas pro (m/s · s) |
| `max_tilt_deg` | 25 | maximale Neigung beim Positionshalten |
| `max_stick` | 0,6 | maximaler Stick-Ausschlag des Autopiloten |

## vJoy-Layout

X = Roll (+ rechts), Y = Pitch (+ vor), Z = Gas (−1 aus … +1 voll), RX = Yaw (+ rechts),
alle anderen Achsen 0.
