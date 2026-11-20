#!/bin/zsh
# EasyPilot Studio mit dem eigenen Simulator (EasyPilot-Sim, autopilot/freefly) statt Liftoff.
# Doppelklick im Finder. Startet, was noch nicht läuft: OpenJoystickDriver (RC 3), Studio, Sim.
# Fenster: Sim oben links, Telemetrie oben rechts, Bedienung unten (wie bei Liftoff).
# Zurück zu Liftoff: im Studio oben auf „Liftoff“ klicken. Beenden: mac/Stop-EasyPilot.command
HERE=${0:A:h}
SIM=${HERE:h}
PY="$SIM/.venv/bin/python"
PORT=8765
URL="http://localhost:$PORT/"
LOG="$HOME/EasyPilot/logs"
mkdir -p "$LOG"
cd "$SIM" || exit 1

say_step() { print -P "%B== $1%b"; }
api() { curl -s -m 5 -X POST "$URL"api/command -d "$1"; echo; }

say_step "OpenJoystickDriver (DJI FPV RC 3)"
if ! pgrep -f "OpenJoystickDriver.app/Contents/MacOS/OpenJoystickDriver" >/dev/null; then
  open -a OpenJoystickDriver 2>/dev/null && sleep 3
fi
OJD=/Applications/OpenJoystickDriver.app/Contents/MacOS/OpenJoystickDriver
if "$OJD" virtual show 2>/dev/null | grep -q "DJI Virtual Joystick.*sdl-compatible"; then
  "$OJD" --no-input --timeout 5 virtual set generic 2CA3:1021 >/dev/null 2>&1 && sleep 2
fi

say_step "Studio"
if ! curl -s -m 2 "$URL"api/state >/dev/null; then
  nohup "$PY" -u -m autopilot.studio --no-browser >>"$LOG/studio.log" 2>&1 &
  for i in {1..30}; do curl -s -m 1 "$URL"api/state >/dev/null && break; sleep 1; done
fi
curl -s -m 5 "$URL"api/sim >/dev/null || { echo "Studio antwortet nicht, siehe $LOG/studio.log"; tail -20 "$LOG/studio.log"; exit 1; }
echo "läuft: $URL"

say_step "EasyPilot-Sim"
api '{"action": "simulator", "which": "sim"}' >/dev/null
api '{"action": "sim_start"}' >/dev/null
for i in {1..40}; do
  up=$(curl -s -m 2 "$URL"api/sim | "$PY" -c 'import json,sys; print(int(json.load(sys.stdin)["sim"]["running"]))' 2>/dev/null)
  [[ "$up" == 1 ]] && break
  sleep 1
done
[[ "$up" == 1 ]] && echo "läuft" || { echo "Sim startet nicht, siehe ~/EasyPilot/runs/studio/sim/freefly.log"; exit 1; }

say_step "Fenster anordnen"
api "{\"action\": \"sim_layout\", \"url\": \"$URL\"}"
echo
echo "Fertig. Im Studio: Wer fliegt, Modus, Autopilot, Tempo k, Runden, dann Start."
