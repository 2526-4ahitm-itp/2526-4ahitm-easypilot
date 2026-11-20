#!/bin/zsh
# Freies Fliegen im eigenen Mini-Simulator (ohne Liftoff, ohne Rennen, ohne Autopilot).
# Doppelklick im Finder. Fliegen mit der DJI FPV RC 3 (oder Tastatur: W/S Gas, A/D Gieren, Pfeile).
# R / Leertaste / Knopf an der Fernsteuerung = Neustart, H = Anzeige, Esc = Ende.
# Fenster statt Vollbild:  mac/Sim-Fliegen.command --window
HERE=${0:A:h}
SIM=${HERE:h}
PY="$SIM/.venv/bin/python"
cd "$SIM" || exit 1

# Die RC 3 kommt über OpenJoystickDriver (Profil "generic") -> autopilot/hid_mac.py
if ! pgrep -f "OpenJoystickDriver.app/Contents/MacOS/OpenJoystickDriver" >/dev/null; then
  open -a OpenJoystickDriver 2>/dev/null && sleep 3
fi
OJD=/Applications/OpenJoystickDriver.app/Contents/MacOS/OpenJoystickDriver
if "$OJD" virtual show 2>/dev/null | grep -q "DJI Virtual Joystick.*sdl-compatible"; then
  "$OJD" --no-input --timeout 5 virtual set generic 2CA3:1021 >/dev/null 2>&1 && sleep 2
fi

"$PY" -m autopilot.freefly "$@" 2> >(grep -v "^objc" >&2)
