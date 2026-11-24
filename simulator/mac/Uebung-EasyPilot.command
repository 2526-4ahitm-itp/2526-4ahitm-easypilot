#!/bin/zsh
# Übungsmodus per Doppelklick: startet EasyPilot (wie Start-EasyPilot.command), wartet auf die
# kalibrierte Fernsteuerung (DJI FPV RC 3) und startet „Mensch fliegt“ ohne Ende: nach einem
# Absturz oder im Ziel geht es vom Start weiter. Enter oder Ctrl+C in diesem Fenster stoppt den Lauf.
# EasyPilot und Liftoff laufen danach weiter (Beenden: Stop-EasyPilot.command).
HERE=${0:A:h}
URL="http://localhost:8765/"
NAME=${1:-Simon}

zsh "$HERE/Start-EasyPilot.command" || exit 1
echo

state() { curl -s -m 3 "$URL"api/state | python3 -c "import json,sys; s=json.load(sys.stdin); $1" 2>/dev/null; }

if [[ "$(state 'print(int(s["liftoff"]["in_level"] and s["liftoff"]["telemetry"]))')" != 1 ]]; then
  echo "Liftoff ist nicht in der Strecke. In Liftoff Quick Play > Last Session wählen, dann Enter."
  read -r
fi

print -P "%B== Fernsteuerung%b"
for i in {1..300}; do
  [[ "$(state 'c=s["controllers"]; print(int(bool(c["connected"]) and c["calibrated"]))')" == 1 ]] && break
  (( i == 1 )) && echo "RC 3 einschalten und an einen runden USB-C-Port hinten stecken (USB-A geht nicht) ..."
  sleep 1
done
if [[ "$(state 'c=s["controllers"]; print(int(bool(c["connected"]) and c["calibrated"]))')" != 1 ]]; then
  echo "Keine kalibrierte Fernsteuerung gefunden (5 min). Kalibrieren.command ausführen."
  exit 1
fi
sleep 3      # OJD braucht nach dem Anstecken einen Moment

stop_run() { curl -s -m 3 -X POST "$URL"api/command -d '{"action":"abort"}' >/dev/null; echo; echo "Übung gestoppt."; exit 0; }
trap stop_run INT

print -P "%B== Übungsmodus%b"
echo "Rechter Stick in die Mitte, Gas ganz unten."
say -v Anna "Übungsmodus startet. Rechter Stick in die Mitte, Gas unten." 2>/dev/null &
curl -s -m 5 -X POST "$URL"api/command -d "{\"action\":\"human\",\"name\":\"$NAME\",\"infinite\":true}" >/dev/null
echo "Läuft. Enter (oder Ctrl+C) stoppt."
( last=""; while true; do
    m=$(state 'print(s["phase"], "-", s["message"])')
    [[ -n "$m" && "$m" != "$last" ]] && { echo "  $m"; last=$m; }
    sleep 1
  done ) &
WATCH=$!
read -r
kill $WATCH 2>/dev/null
stop_run
