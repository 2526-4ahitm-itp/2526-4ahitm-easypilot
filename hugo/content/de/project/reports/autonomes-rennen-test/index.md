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

## After Hours (zweite Strecke, andere Tortypen) – 19.10.2026

Strecke mit Torbögen, zwei MultiGP-Rahmen-Varianten auf Masten und unsichtbaren Checkpoint-Boxen;
Start- und Zieltor sind dasselbe Tor.

| Versuch | Ergebnis | Ursache / Fix |
|---|---|---|
| 60 %, erste Höhenannahme | Liftoff wertet keine Runde | MultiGP-Rahmen hängen auf Masten, Drohne flog unten durch |
| nach Messung (Frame01 4,05 m, Frame02 6,45 m), 60 % | **1:25,684, Platz 1** (28,27 / 28,71 / 28,71 s) | – |
| 80 % | Liftoff wertet nur 2 Runden | Start zu steil: über das Starttor geflogen. Fix: Startlinie gerade und auf Torhöhe, Tempo bis zum ersten Tor begrenzt |
| 80 % | Absturz nach 22 Toren | Nach dem 6,5-m-Rahmen verlangte die Linie mehr Abwärtsbeschleunigung als g; Drohne blieb am nächsten Torbogen hängen. Fix: Abwärtskrümmung auf 0,6 g begrenzt, Absturzerkennung |
| 80 % | **1:17,035, Platz 1** (26,09 / 25,48 / 25,47 s), bester Bot 1:22,5 | eigene Torzählung 70/70 = Liftoff |

Außerdem behoben: Ein gemeinsames Start-/Zieltor wird pro Rundenwechsel nur einmal gezählt
(vorher erwartete die eigene Wertung zwei Durchflüge).

## KI-Torerkennung

| | |
|---|---|
| Daten | 3209 Bilder aus 5 Runden, 7030 Tore automatisch beschriftet |
| Modell | YOLOv8n-Pose, 4 Eckpunkte, 640 px |
| Ergebnis (Validierung, 1067 Bilder) | Box-mAP50 0,79, Eckpunkt-mAP50 0,85, Präzision 0,89, Recall 0,70 |
| Geschwindigkeit | 1,1 ms Inferenz pro Bild (RTX 5060 Ti) |

Der Recall ist niedrig, weil auch sehr weit entfernte, winzige Tore beschriftet sind.

## Nächste Schritte

- Weitere Strecken und Tortypen (aufblasbare Bögen, Checkpoint-Boxen allein).
- Modell mit Bildern von After Hours nachtrainieren, Kartenkorrektur im Flug testen, Overlay.
- GPS-Zielflug in Liftoff testen (bisher nur im eigenen Modell).
- 10 Runden bei 100 % ohne Fehler (M9), Vergleich mit der Bestzeit des Teams.
