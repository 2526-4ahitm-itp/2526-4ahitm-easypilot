#!/bin/zsh
# Echten Controller (z. B. DJI FPV Remote Controller 3 per USB-C) für „Mensch fliegt“ kalibrieren.
# Einmal pro Controller, speichert autopilot/controller.local.json. Das Studio darf dabei laufen.
HERE=${0:A:h}
cd "${HERE:h}" || exit 1
.venv/bin/python -m autopilot.pilot list
echo
.venv/bin/python -m autopilot.pilot calibrate && {
  echo
  echo "Test: Sticks bewegen, die Werte müssen mitlaufen. Gas unten = 0.00, oben = 1.00,"
  echo "rechts / nach vorne = positiv. Beenden mit Ctrl+C."
  .venv/bin/python -m autopilot.pilot test
}
