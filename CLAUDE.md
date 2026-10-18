# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EasyPilot is a drone telemetry and control system for an Austrian school project (4AHITM).

**Current focus — Phase 2 (since 2026-09-14): drone simulation with a physics engine.** A browser-based
web simulator built on the existing 3D viewer in `webinterface/frontend` (React 19 + three.js). Phase 1
(drone control) is finished; the switch happened because the drone's DJI O4 Air Unit is broken, so the
real drone can no longer be flown or tested.

Existing subsystems from Phase 1:

- **ESP32 firmware** (`PlatformIO/Projects/EasyPilotIOS/`) — WebSocket server + UDP beacon broadcaster, MSP to the Betaflight FC
- **iOS app** (`EasyPilotIOS/`) — SwiftUI app that discovers the ESP32, streams telemetry, sends flight commands, and has an on-device flight simulator

## Communication Architecture

```
ESP32 (WiFi)
  ├── UDP broadcast "EASYPILOT:<IP>" every 5s on port 4242  →  iOS discovers IP
  └── WebSocket server on port 81  ←→  iOS sends commands / receives telemetry JSON at 10Hz
```

**Liftoff autopilot** (`simulator/autopilot/`, Python 3.11, Windows): flies official Liftoff races autonomously
(gate poses from the game's track XMLs, racing line, full-speed controller, YOLO gate detection) and plans
low-altitude GPS waypoint flights. Change `2026-10-14-tdot-autonomes-rennen`, FSD §20, README in the folder.
Tests: `cd simulator && python -m unittest discover -s autopilot/tests -t .` (pure Python, run in CI).
Never commit extracted game data (`autopilot/tracks/`) or `runs/`/`models/`.

`webinterface/` holds the Quarkus backend (`GET /api/status`), the Python relay (WebSocket → UDP broadcast, LAN only) and the React + three.js frontend that Phase 2 builds on.

## Deploy iOS App

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild build \
  -project EasyPilotIOS/EasyPilotIOS.xcodeproj \
  -scheme EasyPilotIOS \
  -destination 'id=00008110-001578C00252801E' \
  -derivedDataPath build \
  DEVELOPMENT_TEAM=47D26QX4MF && \
ios-deploy --bundle build/Build/Products/Debug-iphoneos/EasyPilotIOS.app
```

Or use the wrapper: `./deploy.sh [DEVICE_UDID]`

## ESP32 Firmware

**Location:** `PlatformIO/Projects/EasyPilotIOS/`  
**Board:** esp32-c3-supermini  
**Build/flash:** `pio run` / `pio upload` (PlatformIO CLI or IDE)  
**WiFi credentials:** `cp secrets.ini.example secrets.ini` (gitignored) → `load_secrets.py` generates `include/secrets_auto.h` (gitignored) at build time

**Key libraries** (`platformio.ini`):
- `links2004/WebSockets@^2.4.1` — WebSocket server
- `bblanchon/ArduinoJson@^7.0.0` — JSON parsing

**Flight modes** (`src/main.cpp`):
- `MODE_IDLE` — motors at 1000 PWM, no active control
- `MODE_BALANCE` — P-controller on roll/pitch; M1(FL)/M2(FR)/M3(RL)/M4(RR) adjusted around `baseThrottle` using `kPRoll`/`kPPitch`
- `MODE_MANUAL` — motor/attitude values sent directly by iOS
- `MODE_SOUND` — all 4 motors set to PWM from `TILT_SOUND` packets; 1s timeout stops motors
- `MODE_RC` — stick values from the Simulator tab's LIVE mode; same P-controller as BALANCE but with target angles, throttle and yaw from `RC` packets; 500 ms without an `RC` packet stops the motors (`RC_TIMEOUT_MS`)

**Commands received (JSON unless noted):**
| Command | Notes |
|---------|-------|
| `{"cmd":"ARM"}` | Sets `isArmed = true` |
| `{"cmd":"DISARM"}` | Stops motors, resets to IDLE |
| `{"cmd":"STOP"}` | Stops motors, goes to IDLE |
| `{"cmd":"START_BALANCE","baseThrottle":N,"kPRoll":N,"kPPitch":N}` | Starts balance mode |
| `{"cmd":"START_MANUAL",...all telemetry fields...}` | Starts manual mode |
| `{"cmd":"START_SOUND","maxPWM":N}` | Starts sound mode, N capped 1000–1500 |
| `{"cmd":"TILT_SOUND","pwm":N}` | Sets all motors to N; resets 1s timeout |
| `{"cmd":"START_RC","kPRoll":N,"kPPitch":N}` | Starts RC mode (armed only) |
| `{"cmd":"RC","thr":N,"pit":N,"rol":N,"yaw":N}` | Stick packet at 10 Hz; `thr` 1000–2000, `pit`/`rol` ±45°, `yaw` ±100; resets 500 ms timeout |
| JSON without `cmd` | Manual update: overrides attitude/motor/battery values |
| `SAFE_TEST` (plain text) | Runs M1=1050 for 500ms (armed only) |
| `SIMULATE` (plain text) | Re-enables fake telemetry while disarmed and no FC is connected |

**Telemetry broadcast (JSON, 10Hz):**
```json
{"roll":0.0,"pitch":0.0,"yaw":0.0,"m1":1000,"m2":1000,"m3":1000,"m4":1000,
 "voltage":16.8,"batteryPercentage":100,"armed":false,"mode":"IDLE","fc":false}
```
`mode` is one of `IDLE`, `BALANCE`, `MANUAL`, `SOUND`, `RC`. `fc` is true once the Betaflight FC answers MSP.

## iOS App Architecture

**State ownership:** `ContentView` creates exactly one `WebSocketManager` and one `MotionManager` (`@StateObject`) and passes them as `@ObservedObject` to the three tabs: Dashboard, Simulator, Algorithms (`ControlView`). Never create additional instances.

**Key files:**

| File | Role |
|------|------|
| `ContentView.swift` | TabView root, owns `WebSocketManager` + `MotionManager`, calls `start()`/`stop()` |
| `WebSocketManager.swift` | UDP beacon listener → WebSocket client; publishes `telemetry`, `isConnected`, `esp32IP`; `send(_ DroneCommand)` |
| `DroneCommand.swift` | Every command the app sends, with its exact wire payload |
| `FlightMode.swift` | Firmware flight modes (`IDLE`/`BALANCE`/`MANUAL`/`SOUND`); unknown strings fall back to `.idle` — `RC` is missing and shows as IDLE (change `2026-10-13-fix-ios-rc-mode`) |
| `SoundMode.swift` | Tilt → PWM math and emergency threshold for Sound Mode |
| `SimulatorView.swift` | Simulator tab: joysticks, SIM/LIVE toggle; in LIVE sends `START_RC` + `RC` packets at 10 Hz |
| `DroneSimulator.swift` | On-device flight physics (RATE / BALANCE / POS) |
| `SimulatorScene.swift` | SceneKit world for the simulator; drives physics from the render loop |
| `VirtualJoystick.swift` | Circular joystick with expo curve |
| `DashboardView.swift` | Live telemetry display; SceneKit 3D drone model; iPhone motion card; safe-test trigger |
| `ControlView.swift` | Algorithms tab: ARM/DISARM (hold-to-arm 1.5s), mode selector, per-mode config, profile save/load, Sound Mode |
| `DesignSystem.swift` | `EasyPilotTheme`, `GlassCard`, `HorizonIndicator`, `PulsingDot`, `TelemetryCard`, `MotorBar`, `LabeledSlider` |
| `MotionManager.swift` | CoreMotion at 10Hz; publishes `pitch` and `roll` in degrees |
| `DroneTelemetry.swift` | `Codable` struct matching ESP32 telemetry JSON |
| `ControlProfile.swift` | `Codable` profile; builds its `DroneCommand`s |
| `ProfileManager.swift` | Persists profiles to `UserDefaults` (`"easypilot.controlProfiles"`) |

**Sound Mode flow:**
1. iOS tilt angle = `sqrt(pitch² + roll²)`, clamped to 90° (`SoundMode.tiltAngle`)
2. PWM = `1000 + Int((min(tiltAngle, 45°) / 45°) × (maxSoundPWM - 1000))` (`SoundMode.pwm`)
3. Timer fires at 10Hz → sends `TILT_SOUND`; if tilt > 60° → emergency stop (`SoundMode.isEmergency`)
4. ESP32 stops motors if no packet arrives for 1s

## Tests

```bash
# iOS (unit + UI tests, simulator)
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild test \
  -project EasyPilotIOS/EasyPilotIOS.xcodeproj -scheme EasyPilotIOS \
  -destination 'platform=iOS Simulator,name=iPhone 17'

# Backend
cd webinterface/backend && ./mvnw test

# Frontend (lint + build)
cd webinterface/frontend && npm ci && npm run lint && npm run build
```

All three run in GitHub Actions (`.github/workflows/`). The Xcode scheme is shared (`xcshareddata`) so CI can find it.

## Branches & Commits

One branch per topic (`<type>/<topic>`), Conventional Commits with a German subject, one PR per topic — see "Mitarbeit" in `README.adoc`.

## OpenSpec

Requirements document: `spec/fsd.md` (German, sections referenced as `§N.M`). Capability specs live in `openspec/specs/<capability>/spec.md`, one capability per folder, every requirement with `status: implemented | partial | not-implemented` (rules in `openspec/config.yaml`). Active changes: `openspec/changes/2026-10-13-phase2-web-simulator`, `openspec/changes/2026-10-13-fix-ios-rc-mode` and `openspec/changes/2026-10-14-tdot-autonomes-rennen`. `openspec validate --all` must pass; it runs in the OpenSpec workflow. When a change is done, update the status markers it touches and `openspec archive` it. Do not commit changes unless the user explicitly asks.
