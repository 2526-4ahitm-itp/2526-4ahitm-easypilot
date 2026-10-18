---
title: Testbericht autonomes Rennen
date: 2026-10-18
---

## Aufbau

| | |
|---|---|
| Simulator | Liftoff 1.7.6, Level „Straw Bale“, Armattan Mongoose, Acro |
| Programm | `simulator/autopilot`, Regler im Takt der Telemetrie (100 Hz) |
| Ausgabe | vJoy, kein physischer Controller |
| PC | Ryzen 7 7700X, RTX 5060 Ti, Liftoff im 1080p-Fenster, VSync aus |

Alle Flüge hat das Programm allein geflogen, inklusive Menüs, Reset und Rennstart.

## Zwischenstand vor dem Rennen

| Schritt | Ergebnis |
|---|---|
| Erster Schwebeflug mit neuem Regler | 3 m Höhe, Position gehalten; Gas schwankte (VSync = 30 fps) |
| VSync aus, Fenster 1080p | Telemetrie gleichmäßig 100 Hz, Eingabeverzögerung ~20 ms |
| Systemidentifikation | Schwebegas 0,281, Schub ~ Gas², Raten vermessen |
| Kamerakalibrierung | FOV 125°, Uptilt 42°, 0,8 px Restfehler |
| Torposen aus der XML ins Kamerabild projiziert | liegen auf den echten Torbögen |

## Field Day, eine Runde ab Start (Free Flight, eigene Torwertung)

| Tempo | Zeit | Tore | max. Abweichung | Bemerkung |
|---|---|---|---|---|
| 35 % | 39,7 s | 17/17 | 0,30 m | |
| 60 % | 26,2 s | 17/17 | 0,55 m | |
| 70 % | 24,1 s | 17/17 | 1,03 m | Drohne sackt bei Tempo 0,9 m unter die Linie |
| 80 % (vor Fix) | – | 8/17 | Absturz | Luftwiderstand nicht modelliert |
| 80 % (mit Widerstandsmodell) | 24,0 s | 17/17 | 0,49 m | |
| 100 % | **18,7 s** | 17/17 | 1,03 m | Spitze 35 m/s (126 km/h) |

**Fix:** Luftwiderstand (0,033 1/m) im Regler vorgesteuert und in der Geschwindigkeitsplanung
berücksichtigt, Grenze der Störgrößenschätzung von 25 auf 45 m/s² erhöht.

## Field Day, Race-Modus, von Liftoff gewertet

3 Runden bei 80 %: **59,154 s, Platz 1** (Runden 19,58 / 19,63 / 19,63 s).
Liftoff-Bots: Captain Sticktime 1:33,725, Ms Snappy 1:36,380.

## After Hours (zweite Strecke, andere Tortypen)

| Versuch | Ergebnis | Ursache |
|---|---|---|
| 60 %, 3 Runden | eigene Wertung 23/24, Liftoff zählt keine Runde | MultiGP-Rahmen hängen auf Masten, Drohne flog unten durch |
| nach Messung von Frame02 (6,45 m) | Liftoff zählt weiterhin nicht | Variante Frame01 hängt tiefer (4,05 m) |
| Start | einmal Kollision mit dem Startbogen | zu steiler Abflug, jetzt flach |

Offen: Nachweis mit beiden gemessenen Höhen.

## KI-Torerkennung

| | |
|---|---|
| Daten | 3209 Bilder aus 5 Runden, 7030 Tore automatisch beschriftet |
| Modell | YOLOv8n-Pose, 4 Eckpunkte, 640 px |
| Ergebnis (Validierung, 1067 Bilder) | Box-mAP50 0,79, Eckpunkt-mAP50 0,85, Präzision 0,89, Recall 0,70 |
| Geschwindigkeit | 1,1 ms Inferenz pro Bild (RTX 5060 Ti) |

Der Recall ist niedrig, weil auch sehr weit entfernte, winzige Tore beschriftet sind.

## Nächste Schritte

- After Hours im Race-Modus nachweisen, danach weitere Strecken.
- Modell mit Bildern von After Hours nachtrainieren, Kartenkorrektur im Flug testen, Overlay.
- GPS-Zielflug in Liftoff testen (bisher nur im eigenen Modell).
- 10 Runden bei 100 % ohne Fehler (M9), Vergleich mit der Bestzeit des Teams.
