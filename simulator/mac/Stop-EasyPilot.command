#!/bin/zsh
# Studio, Präsentationsmodus und ojdpad beenden. Liftoff und OpenJoystickDriver bleiben offen.
stop() {
  pgrep -f "$1" >/dev/null || return 0
  pkill -f "$1"
  for i in {1..10}; do pgrep -f "$1" >/dev/null || { echo "$2 beendet"; return 0; }; sleep 0.5; done
  pkill -9 -f "$1" && echo "$2 hart beendet"     # hängt gelegentlich (19.11.: Studio reagierte nicht auf TERM)
}
stop "mac/kiosk.py" "Präsentationsmodus"
stop "autopilot.studio" "Studio"
stop "autopilot[.]freefly --window --size [0-9]+x[0-9]+ --remote" "EasyPilot-Sim (vom Studio)"   # genau der Aufruf aus studio_sim.py
stop "mac/ojdpad.py" "ojdpad"
true
