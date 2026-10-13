---
title: Liftoff-Hover einrichten
weight: 5
---

Voraussetzung: Windows, Liftoff (Steam), Python 3.11, Funk-Controller per USB.

{{% steps %}}

### vJoy installieren

[vJoy 2.2.2.0](https://github.com/BrunnerInnovation/vJoy/releases) installieren und Gerät 1 auf
8 Achsen und 32 Knöpfe stellen (Admin-Konsole):

```bat
"C:\Program Files\vJoy\x64\vJoyConfig.exe" 1 -f -a x y z rx ry rz sl0 sl1 -b 32
```

### Telemetrie in Liftoff einschalten

Datei `%USERPROFILE%\AppData\LocalLow\LuGus Studios\Liftoff\TelemetryConfiguration.json`:

```json
{
  "EndPoint": "127.0.0.1:9001",
  "StreamFormat": ["Timestamp", "Position", "Attitude", "Gyro", "Input"]
}
```

Liftoff lädt sie bei jedem Drohnen-Reset neu.

### Controller kalibrieren

```bat
cd simulator\liftoff-hover
py -3.11 -m pip install pygame
py -3.11 hover.py calibrate
```

Den Anweisungen folgen: Gas hoch, Yaw rechts, Pitch vor, Roll rechts, dann den Hover-Knopf
drücken. Das Ergebnis landet in `config.json`.

### vJoy in Liftoff zuordnen

Options → Controls → Controller → *Select* → „vJoy – Virtual Joystick“. Achsen: X = Roll,
Y = Pitch, Z = Gas, RX = Yaw. Bleibt Liftoffs Assistent bei „Center all sticks“ hängen, die
Zuordnung direkt in die Datei unter `...\Liftoff\InputSettings\<id>\*.inputsettings` schreiben
(siehe [README](https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot/tree/main/simulator/liftoff-hover)).

### Starten

```bat
start.bat
```

Ins Liftoff-Fenster klicken, damit Liftoff Eingaben annimmt. Dann fliegen und den Hover-Knopf drücken.

{{% /steps %}}

Zum Fehlersuchen zeigt `py -3.11 hover.py monitor` Rohwerte und Telemetrie live an.
