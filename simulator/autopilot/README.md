# Autopilot für Liftoff – autonomes Rennen und Zielflug (Phase 2)

Python-Autopilot, der die Drohne im FPV-Simulator **Liftoff** selbst fliegt: durch alle
Torbögen einer Rennstrecke so schnell wie möglich, und (in Arbeit) zu einer GPS-Koordinate
ohne Kollision. Ziel ist das Rennen „Schüler:innen gegen das Programm“ am Tag der offenen Tür
(Pflichtenheft §20, Change `openspec/changes/2026-10-14-tdot-autonomes-rennen`).

```
Liftoff ──UDP 100 Hz (Position, Lage, Geschwindigkeit)──► telemetry.py
   ▲                                                         │
   │ vJoy (Sticks, Reset, Menü)                              ▼
vjoy.py ◄── control.py (Schubvektor → Drehraten → Sticks) ◄── racer.py ◄── planner.py (Rennlinie)
                                                             ▲              ▲
FPV-Bild ── capture.py ──► detector.py (YOLO, 4 Eckpunkte) ──┘   track.py (Tore aus Liftoff-XML)
```

## Stand (18.10.2026)

| Was | Ergebnis |
|---|---|
| Rennen „01 – Field Day“ (Straw Bale), Race-Modus, 3 Runden, 80 % | **59,154 s, Platz 1** – von Liftoff gewertet; beste Liftoff-Bots 1:33,7 |
| Eine Runde Field Day bei 100 % | 18,7 s, Spitze 35 m/s (126 km/h), alle 17 Tore |
| Rennen „02 – After Hours“ | eigene Wertung 23/24 Tore; Liftoff wertet noch nicht (MultiGP-Rahmen, Höhe inzwischen vermessen, Nachweis offen) |
| KI-Torerkennung | YOLOv8n-Pose, 3209 automatisch beschriftete Bilder, Box-mAP50 0,79, Eckpunkte 0,85, 1,1 ms pro Bild; Live-Korrektur gebaut, im Flug noch nicht getestet |
| GPS-Zielflug | im eigenen Modell: 10 von 10 Zielen erreicht, 0 Kollisionen, Höhe 1,2–1,6 m (Ziele in Hindernissen → nächster erreichbarer Punkt); in Liftoff noch nicht getestet |

## Einrichten (einmalig)

1. Python 3.11, `pip install numpy opencv-python UnityPy ultralytics` und PyTorch mit CUDA.
2. vJoy 2.2.2.0, Gerät 1 mit 8 Achsen und 32 Knöpfen (wie bei `liftoff-hover`).
3. **Liftoff-Controllerdatei für vJoy** um Menü-, Reset- und Pause-Knöpfe ergänzen (Liftoff
   geschlossen). Belegung siehe `vjoy.py`; die Rewired-IDs stehen in der Hugo-Referenz.
4. `TelemetryConfiguration.json` in `%USERPROFILE%\AppData\LocalLow\LuGus Studios\Liftoff`:
   ```json
   {"EndPoint": "127.0.0.1:9001", "StreamFormat": ["Timestamp", "Position", "Attitude", "Gyro", "Input", "Velocity"]}
   ```
5. Liftoff `Config/System.xml`: `VSyncMode` 0, Motion Blur aus. Fenster 1920×1080 (sonst nur 30 fps
   und ~80 ms Eingabeverzögerung).
6. Strecken extrahieren: `python -m autopilot.track extract` (aus den Spieldateien, nicht im Repo).
7. Drohne vermessen: `python -m autopilot.sysid` (Free Flight) und `python -m autopilot.calib_cam`.
   Ergebnisse stehen in `drone.json` (aktuell Armattan Mongoose).

## Benutzen

Alle Befehle aus `simulator/`. Liftoff muss im Vordergrund sein; **kein** externes Screenshot-Tool
während des Flugs (nimmt Unity den Fokus).

| Befehl | Zweck |
|---|---|
| `python -m autopilot.race StrawBaleRace01 0.8 3` | Rennen fliegen: Name, Tempo 0–1, Runden |
| `python -m autopilot.track show StrawBaleRace02` | Tore eines Rennens anzeigen |
| `python -m autopilot.menu pause` / `ok` / `down` | Liftoff-Menüs per vJoy |
| `python -m autopilot.ui out.jpg 646,463` | Mausklick in Liftoff + eigenes Bildschirmfoto |
| `python -m autopilot.dataset collect StrawBaleRace01 0.5 0.8` | Runden mit Bildern aufnehmen |
| `python -m autopilot.dataset label` | Bilder automatisch beschriften (Torposen + Telemetrie) |
| `python -m autopilot.train_detector 60` | YOLO-Modell trainieren → `models/gates.pt` |
| `python -m autopilot.hovertest` | Kurzer Schwebetest |
| F9 | Not-Aus während eines Flugs |

Logs, Bilder, Datensatz und Modelle landen in `runs/` und `models/` (nicht versioniert).

## Tests

```bash
cd simulator
python -m unittest discover -s autopilot/tests -t . -v
```

Rate-Kurve, Rennlinie und Regler im geschlossenen Kreis bis volle Geschwindigkeit (auch mit
falschem Schwebegas, Wind und Widerstand), GPS-Umrechnung, A*-Planung und Zielflug mit
simuliertem Tiefensensor auf 10 Hinderniskarten.

## Module

| Datei | Inhalt |
|---|---|
| `telemetry.py` | UDP-Empfang nach `TelemetryConfiguration.json`, Verlauf für Bild-Pose-Zuordnung |
| `vjoy.py`, `window.py`, `menu.py`, `ui.py`, `look.py` | Ausgabe an Liftoff, Fokus, Menüsteuerung |
| `liftoff.py` | Sitzung mit Sicherheitsabbruch (Telemetrie weg, Fokus weg, Reset, F9) und Log |
| `rates.py`, `sysid.py`, `calib_cam.py`, `camera.py`, `drone.json` | Drohnenmodell und Kamera |
| `control.py` | Renn-Regler ohne Neigungsgrenze, Luftwiderstand, Störgrößenschätzung |
| `planner.py`, `racer.py`, `race.py` | Rennlinie, Geschwindigkeitsprofil, Torwertung, Renn-Ablauf |
| `track.py` | Rennen/Strecken aus Liftoffs XML, Maße und Bezugspunkte der Tortypen |
| `dataset.py`, `train_detector.py`, `detector.py`, `vision.py` | KI-Torerkennung und Kartenkorrektur |
| `nav.py` | GPS-Zielflug: Umrechnung, Belegungsgitter, A*, Bremsweg-Regel |
| `sim.py`, `tests/` | Liftoff-ähnliches Modell und Tests |
