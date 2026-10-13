# Liftoff Hover – Physik-Simulator-Prototyp (Phase 2)

Eine Middleware, die einer Drohne im FPV-Simulator **Liftoff** ein DJI-artiges
Schweben beibringt: Ein Knopf am Controller, und die Drohne bremst ab und hält
Position, Höhe und Blickrichtung. Nochmal drücken, und man fliegt wieder selbst.

Liftoff rechnet die Physik (500 Hz), dieses Skript ist der Autopilot obendrauf.
So lassen sich Regelalgorithmen für EasyPilot testen, obwohl die echte Drohne
seit dem Defekt der DJI O4 Air Unit nicht mehr fliegt.

```
Funk-Controller ──► hover.py ──► vJoy (virtueller Joystick) ──► Liftoff
                       ▲                                           │
                       └──── UDP-Telemetrie (Position, Lage) ◄─────┘
```

- **Manuell:** Die Sticks gehen 1:1 an vJoy, nur auf ein festes Layout normiert.
- **Hover:** Das Skript ignoriert die Sticks und regelt selbst, 250-mal pro Sekunde:
  - Position → Soll-Neigung
  - Neigung → Pitch/Roll-Stick (Acro-Rate)
  - Höhe → Soll-Steigrate → Gas, mit Integral gegen ein falsch geschätztes Schwebegas
  - Heading → Yaw

## Voraussetzungen

| Was | Wofür |
|---|---|
| Windows, Liftoff (Steam) | Simulator |
| [vJoy 2.2.2.0](https://github.com/BrunnerInnovation/vJoy/releases) | virtueller Joystick, Gerät 1 mit 8 Achsen und 32 Knöpfen (`vJoyConfig 1 -f -a x y z rx ry rz sl0 sl1 -b 32`) |
| Python 3.11 + `pygame` | Controller lesen |
| Funk-Controller per USB | getestet mit dem DJI-Controller des Teams |

## Einrichten

1. **Telemetrie in Liftoff einschalten.** Lege `TelemetryConfiguration.json` in
   `%USERPROFILE%\AppData\LocalLow\LuGus Studios\Liftoff` an:

   ```json
   {
     "EndPoint": "127.0.0.1:9001",
     "StreamFormat": ["Timestamp", "Position", "Attitude", "Gyro", "Input"]
   }
   ```

2. **Controller kalibrieren.** Folge den Anweisungen im Terminal. Ergebnis ist `config.json`
   (lokal, nicht im Repo; `config.example.json` zeigt das Format).

   ```bat
   py -3.11 -m pip install pygame
   py -3.11 hover.py calibrate
   ```

3. **In Liftoff vJoy als Controller wählen** und so zuordnen:
   X = Roll, Y = Pitch, Z = Gas, RX = Yaw.

4. **Starten:** `start.bat`, oder `py -3.11 hover.py`. Ins Liftoff-Fenster klicken, losfliegen,
   den Hover-Knopf drücken.

`py -3.11 hover.py monitor` zeigt die Rohwerte und die Telemetrie live an, zum Fehlersuchen.

## Tests

```bash
cd simulator/liftoff-hover
python -m unittest -v test_hover.py
```

Die Tests prüfen den Regler im geschlossenen Kreis mit einem kleinen Drohnenmodell:
- Abbremsen aus 6 m/s
- Halten von Position, Höhe und Heading
- falsch geschätztes Schwebegas
- Stick-Grenzen
- Lage-Konventionen der Unity-Quaternionen

Sie laufen in GitHub Actions (`.github/workflows/simulator.yml`).

## Stolperfallen

- **Liftoff liest Controller nur, wenn sein Fenster den Fokus hat.** Wer zwischendurch woanders
  tippt, kann nicht armen.
- **Armen:** nur den Gasstick nach unten. Den DJI-typischen Griff mit beiden Sticks nach unten
  innen kennt Liftoff nicht.
- **Liftoffs Kalibrier-Assistent bleibt bei „Center all sticks“ hängen**, wenn eine Achse in
  Ruhe nicht genau 0 liefert. Dann die Zuordnung direkt in die `.inputsettings`-Datei unter
  `...\Liftoff\InputSettings\` schreiben.
- **Nach einem Liftoff-Update** wird eine alte Controller-Datei eventuell nicht mehr erkannt.
  Liftoff legt dann eine leere Zuordnung an, und die Drohne lässt sich nicht armen.
- **Zurück auf manuell:** Der Gasstick zentriert nicht. Er sollte ungefähr auf Schwebegas stehen
  (Anzeige `thr man` vs. `hover`), sonst steigt oder fällt die Drohne nach der 0,5-s-Überblendung.

## Ergebnisse

Im Test in Liftoff (Free Flight, Standard-Drohne) wurde Hover im Steigflug mit 16 m/s
eingeschaltet. Die Drohne war nach ~2 s abgebremst und stand nach ~5 s. Danach driftete sie
weder horizontal noch in der Höhe messbar. Das Schwebegas pendelte sich bei 28 % ein.
