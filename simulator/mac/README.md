# Liftoff-Autopilot auf macOS

Der Autopilot (`simulator/autopilot`) läuft auch auf einem Mac (Apple Silicon, macOS 15),
mit Liftoff aus Steam für macOS. Die Logik ist dieselbe; nur die Anbindung an das Betriebssystem
ist ausgetauscht:

| Windows | macOS | Datei |
|---|---|---|
| vJoy-Treiber | OpenJoystickDriver-Gamepad („Xbox Wireless Controller“), gehalten von `ojdpad.py` | `mac/ojdpad.py`, `autopilot/vjoy.py` |
| `user32` (Fenster, Fokus, Klicks) | Quartz + AppKit | `autopilot/window_mac.py` |
| GDI StretchBlt | mss + OpenCV | `autopilot/capture_mac.py` |
| `AppData/LocalLow/...` | `~/Library/Application Support/LuGus Studios/Liftoff` | `autopilot/paths.py` |
| F9 | F9 (bzw. fn+F9) | `autopilot/window_mac.py` |

```
Liftoff ──UDP :9001 (Telemetrie)──► autopilot (MacVJoy)
   ▲                                     │ UDP :9101, 20 Byte pro Zustand
   └── Gamepad „Xbox Wireless Controller“ ◄── mac/ojdpad.py ── ojd virtual feed
```

macOS lässt ein selbst gebautes virtuelles HID-Gerät nur mit einer Apple-Freigabe zu, auch mit
`sudo` nicht. OpenJoystickDriver ist notarisiert und darf das. `ojdpad.py` hält das Gamepad
dauerhaft offen wie der vJoy-Treiber unter Windows. Verschwindet das Gamepad, liest Liftoff einen
mittigen Trigger, also halbes Gas, und die Drohne steigt weg. Kommt 0,5 s kein Paket, setzt
`ojdpad` Gas aus und die Sticks in die Mitte. Es braucht keinen Mod im Spiel und kein `sudo`.

## Einrichten (einmalig)

1. Steam für macOS installieren, Liftoff installieren und einmal starten (legt den Datenordner an).
2. ```bash
   simulator/mac/setup.sh            # --vision zusätzlich für die YOLO-Torerkennung
   ```
   Legt `simulator/.venv` (Python 3.11) an und schreibt
   `TelemetryConfiguration.json` nach `~/Library/Application Support/LuGus Studios/Liftoff`.
3. **Systemeinstellungen > Datenschutz & Sicherheit** für das Terminal (bzw. die App, aus der
   Python läuft): **Bedienungshilfen** (Klicks, Fenster) und **Bildschirmaufnahme** (Kamera-Bild,
   Fenstergröße).
4. OpenJoystickDriver installieren (getestet: 0.6.0-alpha.2,
   https://github.com/xsyetopz/OpenJoystickDriver/releases), starten und unter
   **Datenschutz & Sicherheit** **Eingabeüberwachung** und **Bedienungshilfen** erlauben.
   CLI verlinken: `ln -s /Applications/OpenJoystickDriver.app/Contents/MacOS/OpenJoystickDriver /opt/homebrew/bin/ojd`.
   Test: `ojd status`, dann `hidutil list | grep -i openjoystick` während ein Autopilot-Befehl läuft.
5. `ojdpad` starten und laufen lassen:
   `simulator/.venv/bin/python simulator/mac/ojdpad.py`
6. **Liftoff > Options > Controls > Controller > Calibrate > Manual Calibration.** Beim Wählen
   jedes Kanals müssen alle Achsen in der Mitte stehen. Kanäle:
   - Right horizontal = 0 (Roll)
   - Right vertical = 3 (Pitch)
   - Left vertical = 4 (Gas)
   - Left horizontal = 5 (Yaw)

   Jede Achse einmal ganz durchfahren und das Deadband auf 0 stellen. Danach Mode 2 und Save.
   Belegung und Vorzeichen stehen in `OjdGamepad` in `autopilot/vjoy.py`.
7. **Controls > Buttons:** „FPV Noise Toggle“ (Left Trigger) und „Fisheye Toggle“ (Right Trigger)
   mit Clear Key leeren, dann Save. Die übrigen Xbox-Standardknöpfe passen:
   - A = Bestätigen
   - B = Zurück bzw. Reset
   - Guide = Pause
   - Y = Exit
8. Liftoff-Grafik (getestet auf M1): 1920×1080, Quality Fast, VSync aus, Bloom, AO, DOF, AA und Motion Blur aus.
9. Strecken und Drohne wie unter Windows (alle Befehle in `simulator/`):
   ```bash
   .venv/bin/python -m autopilot.track extract
   .venv/bin/python -m autopilot.sysid
   ```

## Benutzen

OpenJoystickDriver muss laufen (Menüleiste), dazu `ojdpad.py` in einem eigenen Terminal.
Liftoff muss im Vordergrund sein. Dann wie in `autopilot/README.md`, nur mit `.venv/bin/python`:

```bash
cd simulator
.venv/bin/python -m autopilot.hovertest
.venv/bin/python -m autopilot.race StrawBaleRace01 0.8 3
.venv/bin/python -m autopilot.studio
.venv/bin/python -m unittest discover -s autopilot/tests -t . -v   # ohne Liftoff
```

## Studio (Demo für den Tag der offenen Tür)

`autopilot/studio.py` läuft auch am Mac. Vorher müssen OpenJoystickDriver und `ojdpad.py` laufen,
und die Strecken müssen einmal extrahiert sein (`.venv/bin/python -m autopilot.track extract`).

```bash
cd simulator
.venv/bin/python -m autopilot.studio            # http://localhost:8765/
```

Was am Mac anders ist:

- **Liftoff im Fenstermodus** (Unity-Prefs, Liftoff vorher beenden):
  `defaults write "$HOME/Library/Preferences/unity.LuGus Studios.Liftoff.plist" "Screenmanager Fullscreen mode" -int 3`.
  Die Auflösung zählt in Pixeln, auf einem Retina-Bildschirm ergibt 2560×1440 ein Fenster mit
  1280×720 Punkten. Im Vollbild verdeckt Liftoff alles, und man kommt nicht mehr zu anderen Apps.
- **DJI-FPV-DLC:** Die Bedingungen einmal akzeptieren. Abgelehnt erscheint der Dialog bei jedem
  Start wieder und blockiert das Laden der Strecke.
- **Mensch fliegt:** Der Controller wird über pygame gelesen. Das virtuelle Gamepad wird
  herausgefiltert (`pilot._is_virtual`), getestet ist das mit einem echten Controller noch nicht.
- Getestet am 18.11.2026: StrawBaleRace01 wird über das Studio geladen (~50 s). Autopilot Stufe 3:
  17/17 Tore, 34,08 s.

## Grenzen

- Liftoff bleibt im Fenstermodus oder Vollbild; `studio` kann das Fenster unter macOS nur
  verschieben, nicht randlos und immer im Vordergrund machen.
- Die Aufnahme braucht ~30 ms pro Bild (Windows ~17 ms); für die Torerkennung reicht das.
- `liftoff-hover` (pygame + vJoy-Variante) ist noch nicht portiert.
- Sieht Liftoff das Gerät nicht: `ojd status` (Berechtigungen) und `hidutil list | grep -i openjoystick`.
- Unter macOS weckt das Telemetrie-Paket die Regelschleife (`Session._idle`). Kurze Sleeps eines
  Hintergrundprozesses dauern dort ~80 ms, sonst läuft die Regelung nur mit 14 Hz statt ~98 Hz.
- Getestet am 18.11.2026: `hovertest 14 3 3` steigt auf 3 m, fliegt 3 m / 3 m und hält. Reset
  funktioniert, Pause und `race` sind ungetestet.
- Nicht verwenden: das OJD-Profil `generic` (Achsen bleiben 0) und zwei Flugachsen auf einem Stick
  (Rewired begrenzt den Stick auf einen Kreis).
- Nicht verwenden: einen BepInEx-Mod. Liftoff enthält ACTk und meldet „Custom code injection detected“.
