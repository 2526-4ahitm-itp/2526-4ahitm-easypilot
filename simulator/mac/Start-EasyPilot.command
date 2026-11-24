#!/bin/zsh
# EasyPilot Studio am Mac mit einem Doppelklick starten (Finder öffnet .command im Terminal).
# Startet, was noch nicht läuft: OpenJoystickDriver, ojdpad, Studio. Lädt die zuletzt gewählte
# Strecke in Liftoff (Studio startet Liftoff dafür selbst) und ordnet die drei Fenster an:
# Liftoff oben links, Autopilot oben rechts, Bedienung unten.
# Läuft schon alles, ordnet ein Doppelklick nur die Fenster neu an.
HERE=${0:A:h}
SIM=${HERE:h}
PY="$SIM/.venv/bin/python"
PORT=8765
URL="http://localhost:$PORT/"
LOG="$HOME/EasyPilot/logs"
mkdir -p "$LOG"
cd "$SIM" || exit 1

say_step() { print -P "%B== $1%b"; }
running() { pgrep -f "$1" >/dev/null; }
api() { curl -s -m 5 -X POST "$URL"api/command -d "$1"; echo; }

say_step "OpenJoystickDriver"
if ! running "OpenJoystickDriver.app/Contents/MacOS/OpenJoystickDriver"; then
  open -a OpenJoystickDriver || { echo "OpenJoystickDriver fehlt (siehe mac/README.md)"; exit 1; }
  sleep 3
fi
echo "läuft"

say_step "virtuelles Gamepad (ojdpad)"
if ! running "mac/ojdpad.py"; then
  nohup "$PY" -u mac/ojdpad.py >>"$LOG/ojdpad.log" 2>&1 &
  sleep 2
fi
running "mac/ojdpad.py" && echo "läuft" || { echo "ojdpad startet nicht, siehe $LOG/ojdpad.log"; tail -5 "$LOG/ojdpad.log"; exit 1; }

say_step "Studio"
fresh=0
if ! curl -s -m 2 "$URL"api/state >/dev/null; then
  nohup "$PY" -u -m autopilot.studio --no-browser >>"$LOG/studio.log" 2>&1 &
  for i in {1..30}; do curl -s -m 1 "$URL"api/state >/dev/null && break; sleep 1; done
  fresh=1
  sleep 4      # erste Telemetrie abwarten, sonst gilt ein laufendes Rennen als "nicht im Level"
fi
state=$(curl -s -m 5 "$URL"api/state) || { echo "Studio antwortet nicht, siehe $LOG/studio.log"; tail -20 "$LOG/studio.log"; exit 1; }
echo "läuft: $URL"

# Liftoff im Rennen? Steht das Pausenmenü offen, kommt keine Telemetrie: einmal "Resume" klicken.
in_level() {
  curl -s -m 5 "$URL"api/state | "$PY" -c 'import json,sys; s=json.load(sys.stdin)["liftoff"]; print(int(bool(s["running"] and s["in_level"])))' 2>/dev/null
}
liftoff_running() {
  curl -s -m 5 "$URL"api/state | "$PY" -c 'import json,sys; print(int(json.load(sys.stdin)["liftoff"]["running"]))' 2>/dev/null
}
resume() {
  "$PY" -c 'from autopilot import window, ui; window.focus_liftoff(hard=False); ui.click_capture(648, 243)' 2>/dev/null
  sleep 2
}
race=$(print -r -- "$state" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["settings"]["race"])' 2>/dev/null)
if [[ "$(in_level)" != 1 && "$(liftoff_running)" == 1 ]]; then
  resume
fi
if [[ "$(in_level)" != 1 ]]; then
  say_step "Liftoff lädt $race (ca. 1 min)"
  api "{\"action\": \"map\", \"race\": \"$race\"}"
  for i in {1..120}; do
    phase=$(curl -s -m 2 "$URL"api/state | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["phase"])' 2>/dev/null)
    [[ "$phase" == loading || -z "$phase" ]] || break
    sleep 1
  done
  sleep 2
  [[ "$(in_level)" == 1 ]] || resume
fi
[[ "$(in_level)" == 1 ]] && echo "Liftoff ist im Rennen ($race)" || echo "ACHTUNG: Liftoff nicht im Rennen - im Studio unter Strecken neu laden"

if [[ "$MODE" == praesi ]]; then
  say_step "Präsentationsmodus (randlos, ohne Dock)"
  api '{"action": "layout", "mode": "quarter"}'       # nur Liftoff, keine Safari-Fenster
  osascript -e 'tell application "Safari" to close (every window whose URL of current tab starts with "http://localhost:'$PORT'")' 2>/dev/null
  pkill -f "mac/kiosk.py"
  nohup "$PY" -u mac/kiosk.py "$URL" >>"$LOG/kiosk.log" 2>&1 &
  sleep 2
  running "mac/kiosk.py" && echo "läuft (Esc oder Stop-EasyPilot.command beendet ihn)" || tail -5 "$LOG/kiosk.log"
else
  say_step "Fenster anordnen"
  pkill -f "mac/kiosk.py"
  api "{\"action\": \"layout\", \"mode\": \"quarter\", \"url\": \"$URL\"}"
fi

# Liftoff nach vorne, sonst verdecken andere Fenster (Terminal, Finder) das Liftoff-Bild
"$PY" -c 'from autopilot import window; window.focus_liftoff(hard=False)' 2>/dev/null

say_step "Controller für „Mensch fliegt“"
# OJD hält die DJI FPV RC 3 exklusiv. Profil "generic" reicht alle Achsen an ein virtuelles Pad
# weiter, das autopilot/hid_mac.py per IOKit liest (+0,5 ms). Gilt pro Modell, bleibt gespeichert.
OJD=/Applications/OpenJoystickDriver.app/Contents/MacOS/OpenJoystickDriver
if "$OJD" virtual show 2>/dev/null | grep -q "DJI Virtual Joystick.*sdl-compatible"; then
  "$OJD" --no-input --timeout 5 virtual set generic 2CA3:1021 >/dev/null 2>&1 && sleep 2
fi
curl -s -m 5 "$URL"api/state | "$PY" -c '
import json, sys
c = json.load(sys.stdin)["controllers"]
if not c["connected"]:
    print("keiner angesteckt (DJI FPV RC 3 per USB-C anstecken, dann im Studio prüfen)")
elif not c["calibrated"]:
    print("gefunden:", ", ".join(c["connected"]), "- noch nicht kalibriert: mac/Kalibrieren.command doppelklicken")
else:
    print("bereit:", ", ".join(c["connected"]))'

echo
echo "Fertig. Logs: $LOG   Beenden: mac/Stop-EasyPilot.command"
