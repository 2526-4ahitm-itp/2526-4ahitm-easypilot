---
title: "Autonomes Rennen einrichten und starten"
weight: 7
---

Ziel: Das Programm fliegt ein Liftoff-Rennen allein. Dauer beim ersten Mal ~30 min.

## Voraussetzungen

- Windows-PC mit Liftoff (Steam), NVIDIA-GPU für die Torerkennung
- vJoy 2.2.2.0, Gerät 1 mit 8 Achsen und 32 Knöpfen (wie beim [Liftoff-Hover](../liftoff-hover-einrichten))
- Python 3.11 mit `numpy opencv-python UnityPy ultralytics` und PyTorch mit CUDA

## 1. Liftoff vorbereiten (Liftoff geschlossen)

1. **Telemetrie** – `%USERPROFILE%\AppData\LocalLow\LuGus Studios\Liftoff\TelemetryConfiguration.json`:
   ```json
   {"EndPoint": "127.0.0.1:9001",
    "StreamFormat": ["Timestamp", "Position", "Attitude", "Gyro", "Input", "Velocity"]}
   ```
   `Velocity` steht hinten, damit `liftoff-hover` weiter funktioniert.
2. **Grafik** – in `Config\System.xml` `VSyncMode` auf `0`, `Motion_Blur_On` auf `False`.
3. **Fenster** – Liftoff im Fenstermodus 1920×1080 (nicht maximiert).
4. **vJoy-Knöpfe** – in der vJoy-Controllerdatei unter `InputSettings\` die Knöpfe ergänzen
   (Belegung in der [Referenz](../../reference/liftoff-autopilot#vjoy-belegung)). Vorher Backup anlegen.

## 2. Strecken und Drohne

```bash
cd simulator
python -m autopilot.track extract          # Rennen/Strecken aus den Spieldateien
python -m autopilot.track show StrawBaleRace01
```

Liftoff starten, **Free Flight** auf einer freien Fläche, gewünschte Drohne wählen, dann:

```bash
python -m autopilot.sysid        # Schwebegas, Schubkurve, Raten (~40 s Flug)
python -m autopilot.calib_cam    # Kamera-FOV und -Neigung (~60 s, dreht sich auf der Stelle)
```

Die Werte in `autopilot/drone.json` eintragen (für die Mongoose sind sie schon da).

## 3. Rennen fliegen

1. In Liftoff **Race** wählen, Strecke und Drohne einstellen, starten.
2. Nichts mehr am PC anklicken – Liftoff braucht den Fokus.
3. ```bash
   python -m autopilot.race StrawBaleRace01 0.6 3
   ```
   Name des Rennens, Tempo 0–1, Runden. Erst langsam, dann steigern (0,6 → 0,8 → 1,0).
4. **F9** bricht sofort ab (Gas aus). Ohne Telemetrie, bei Fokusverlust oder Reset stoppt das
   Programm ebenfalls selbst.

Ergebnis: Ausgabe im Terminal, Log unter `autopilot/runs/`, offizielle Zeit im Liftoff-Zielbildschirm.

## 4. Torerkennung trainieren (optional)

```bash
python -m autopilot.dataset collect StrawBaleRace01 0.4 0.7 1.0   # Runden mit Bildern
python -m autopilot.dataset label                                # automatisch beschriften
python -m autopilot.train_detector 60                            # ~35 min auf der RTX 5060 Ti
```

## Fehlerbilder

| Symptom | Ursache / Abhilfe |
|---|---|
| Menüs reagieren nicht | Unity hat keinen echten Fokus: Liftoff-Fenster einmal anklicken |
| „telemetry stale“ | kein Level geladen oder Telemetrie-Datei falsch |
| „Liftoff lost focus“ | anderes Fenster im Vordergrund (Explorer, Benachrichtigung) |
| Runde wird von Liftoff nicht gezählt | Bezugspunkt eines Tortyps falsch, siehe [Erklärung](../../explanation/autonomes-rennen) |
