#!/bin/zsh
# One-time macOS setup for the Liftoff autopilot (replaces steps 1-4 of autopilot/README.md on Windows).
#   simulator/mac/setup.sh            # Python env, Liftoff telemetry config
#   simulator/mac/setup.sh --vision   # plus ultralytics (YOLO gate detection, large download)
set -e
HERE=${0:A:h}
SIM=${HERE:h}
LIFTOFF_USER="$HOME/Library/Application Support/LuGus Studios/Liftoff"

echo "== Python 3.11 env in simulator/.venv"
if command -v uv >/dev/null; then
  [[ -d "$SIM/.venv" ]] || uv venv -q --python 3.11 "$SIM/.venv"
  uv pip install -q --python "$SIM/.venv" -r "$SIM/requirements-mac.txt"
  [[ "$1" == "--vision" ]] && uv pip install -q --python "$SIM/.venv" ultralytics
else
  [[ -d "$SIM/.venv" ]] || python3.11 -m venv "$SIM/.venv"
  "$SIM/.venv/bin/pip" install -q -r "$SIM/requirements-mac.txt"
  [[ "$1" == "--vision" ]] && "$SIM/.venv/bin/pip" install -q ultralytics
fi

echo "== OpenJoystickDriver (virtual gamepad)"
if command -v ojd >/dev/null || [[ -x /Applications/OpenJoystickDriver.app/Contents/MacOS/OpenJoystickDriver ]]; then
  echo "found"
else
  echo "missing: install it from https://github.com/xsyetopz/OpenJoystickDriver/releases (see README)"
fi

echo "== Data folder ~/EasyPilot (runs, tracks, models)"
mkdir -p "$HOME/EasyPilot/runs"

echo "== Liftoff telemetry"
mkdir -p "$LIFTOFF_USER"
CFG="$LIFTOFF_USER/TelemetryConfiguration.json"
if [[ -f "$CFG" ]]; then
  echo "exists, left as is: $CFG"
  cat "$CFG"; echo
else
  cat > "$CFG" <<'EOF'
{"EndPoint": "127.0.0.1:9001", "StreamFormat": ["Timestamp", "Position", "Attitude", "Gyro", "Input", "Velocity"]}
EOF
  echo "written: $CFG"
fi

cat <<EOF

Done. Next steps (details in simulator/mac/README.md):
  1. Terminal: Accessibility + Screen Recording in System Settings > Privacy & Security
  2. OpenJoystickDriver running (Input Monitoring + Accessibility), then keep running:
     $SIM/.venv/bin/python $HERE/ojdpad.py
  3. Liftoff > Options > Controls: manual calibration + clear trigger buttons, see mac/README.md
  4. cd $SIM && .venv/bin/python -m autopilot.hovertest
EOF
