# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EasyPilot is a drone telemetry and control system for an Austrian school project (4AHITM). The active Sprint 3 work focuses on two subsystems:

- **ESP32 firmware** (`PlatformIO/Projects/EasyPilotIOS/`) — WebSocket server + UDP beacon broadcaster
- **iOS app** (`EasyPilotIOS/`) — SwiftUI app that discovers the ESP32, streams telemetry, and sends flight commands

## Communication Architecture

```
ESP32 (WiFi)
  ├── UDP broadcast "EASYPILOT:<IP>" every 5s on port 4242  →  iOS discovers IP
  └── WebSocket server on port 81  ←→  iOS sends commands / receives telemetry JSON at 10Hz
```

There is also an older web frontend + Java backend + Python relay in `webinterface/` — these are **not** the active focus and may be outdated.

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
**WiFi credentials:** `secrets.ini` (not committed) → `load_secrets.py` generates `secrets_auto.h`

**Key libraries** (`platformio.ini`):
- `links2004/WebSockets@^2.4.1` — WebSocket server
- `bblanchon/ArduinoJson@^7.0.0` — JSON parsing

**Flight modes** (`src/main.cpp`):
- `MODE_IDLE` — motors at 1000 PWM, no active control
- `MODE_BALANCE` — P-controller on roll/pitch; M1(FL)/M2(FR)/M3(RL)/M4(RR) adjusted around `baseThrottle` using `kPRoll`/`kPPitch`
- `MODE_MANUAL` — motor/attitude values sent directly by iOS
- `MODE_SOUND` — all 4 motors set to PWM from `TILT_SOUND` packets; 1s timeout stops motors

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
| `SAFE_TEST` (plain text) | Runs M1=1050 for 500ms |

**Telemetry broadcast (JSON, 10Hz):**
```json
{"roll":0.0,"pitch":0.0,"yaw":0.0,"m1":1000,"m2":1000,"m3":1000,"m4":1000,
 "voltage":16.8,"batteryPercentage":100,"armed":false,"mode":"IDLE"}
```

## iOS App Architecture

**State ownership:** `ContentView` creates one `@StateObject var wsManager = WebSocketManager()` and passes it as `@ObservedObject` to both tabs. Never create multiple `WebSocketManager` instances.

**Key files:**

| File | Role |
|------|------|
| `ContentView.swift` | TabView root, owns `WebSocketManager`, calls `start()`/`stop()` |
| `WebSocketManager.swift` | UDP beacon listener → WebSocket client; publishes `telemetry`, `isConnected`, `esp32IP` |
| `DashboardView.swift` | Live telemetry display; SceneKit 3D drone model; iPhone motion card; safe-test trigger |
| `ControlView.swift` | ARM/DISARM (hold-to-arm 1.5s), mode selector, per-mode config, profile save/load, Sound Mode |
| `DesignSystem.swift` | `EasyPilotTheme`, `GlassCard`, `HorizonIndicator`, `PulsingDot`, `TelemetryCard`, `MotorBar`, `LabeledSlider` |
| `MotionManager.swift` | CoreMotion at 10Hz; publishes `pitch` and `roll` in degrees |
| `DroneTelemetry.swift` | `Codable` struct matching ESP32 telemetry JSON |
| `ControlProfile.swift` | `Codable` profile with command builder methods |
| `ProfileManager.swift` | Persists profiles to `UserDefaults` (`"easypilot.controlProfiles"`) |

**Sound Mode flow:**
1. iOS tilt angle = `sqrt(pitch² + roll²)`, clamped to 90°
2. PWM = `1000 + Int((min(tiltAngle, 45°) / 45°) × (maxSoundPWM - 1000))`
3. Timer fires at 10Hz → sends `TILT_SOUND`; if tilt > 60° → emergency stop
4. ESP32 stops motors if no packet arrives for 1s

## OpenSpec

Sprint documentation lives in `openspec/changes/sprint-03/`. Do not commit changes unless the user explicitly asks.
