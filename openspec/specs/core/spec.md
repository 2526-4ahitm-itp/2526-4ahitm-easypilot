# Spec: EasyPilot Core

EasyPilot is the 4AHITM Diplomarbeit drone-telemetry-and-control system.
This spec describes the *whole-project* architecture so contributors on
any subsystem have a single starting point. Subsystem-specific behaviour
lives in the other specs under `openspec/specs/`.

## System Map

```
            ┌─────────────────────────┐
            │    iOS app (SwiftUI)    │
            │  - Dashboard tab        │
            │  - Algorithms tab       │
            │  - Simulator tab        │
            └────────────┬────────────┘
                         │
            WiFi  ───────┼───────  ws://<esp32>:81
                         │         UDP :4242 beacon
                         ▼
            ┌─────────────────────────┐
            │  ESP32-C3 SuperMini     │
            │  (EasyPilotIOS/)        │
            │  - WebSocket server     │
            │  - UDP beacon           │
            │  - MSP master           │
            └────────────┬────────────┘
                         │  UART @115200, MSP
                         ▼
            ┌─────────────────────────┐
            │  Betaflight FC          │
            │  - IMU, ESC drivers     │
            └─────────────────────────┘
```

A **second** firmware project (`PlatformIO/Projects/easypilot/`) hosts a
self-contained web dashboard on the ESP32 itself for tethered desk
testing. It does not interact with the iOS app.

## Subsystem Specs

| Spec | What it covers |
|---|---|
| [hardware/](../hardware/spec.md) | ESP32-C3, Betaflight FC, ESCs, battery |
| [firmware/](../firmware/spec.md) | ESP32 flight modes, MSP, watchdogs |
| [communication/](../communication/spec.md) | UDP discovery + WebSocket + MSP protocols |
| [dashboard/](../dashboard/spec.md) | iOS Dashboard tab (live view) |
| [simulator-controller/](../simulator-controller/spec.md) | iOS Simulator tab + virtual joysticks |
| [drone-telemetry/](../drone-telemetry/spec.md) | Attitude + battery telemetry contract |

## ADDED Requirements

### Requirement: System SHALL Provide a Two-Way WiFi Link
The drone and the iOS device SHALL communicate over a single WiFi link
with no manual configuration in the common case.

#### Scenario: Zero-config discovery
- **Given** ESP32 and iPhone are on the same WiFi network
- **When** the iOS app launches
- **Then** it discovers the ESP32 via the UDP beacon and opens the
  WebSocket without prompting the user

#### Scenario: Manual fallback
- **Given** the broadcast does not arrive (AP isolation, mismatched
  subnets, …)
- **When** the user enters the IP in the Dashboard
- **Then** the app uses that IP instead

---

### Requirement: System SHALL Render a Live 3D Visualisation
The iOS app SHALL show a real-time 3D model of the drone driven by
telemetry.

#### Scenario: Load 3D model
- **Given** the iOS app is launched
- **When** the Dashboard view appears
- **Then** the USDZ drone model is loaded into a SceneKit view

#### Scenario: Attitude tracking
- **Given** the WebSocket is delivering telemetry
- **When** roll, pitch, or yaw change
- **Then** the on-screen model rotates accordingly within 200 ms

---

### Requirement: System SHALL Have Three iOS Tabs
The iOS app SHALL expose three tabs in its root `TabView`, each owning
a distinct responsibility:

| Tab | Spec | Purpose |
|---|---|---|
| Dashboard | `dashboard` | Live telemetry, 3D model, sound mode, manual IP |
| Algorithms | `simulator-controller` (historical) | Tune PID/gains, save profiles, send `START_*` |
| Simulator | `simulator-controller` | Phone-side physics + virtual joysticks |

#### Scenario: Single WebSocketManager
- **Given** the iOS app launches
- **Then** `ContentView` owns a single `@StateObject WebSocketManager`
  passed to all tabs as `@ObservedObject`
- **And** no tab creates its own `WebSocketManager` instance

---

### Requirement: System SHALL Fail Safe by Default
The end-to-end system SHALL default to motors-off whenever anything
goes wrong.

#### Scenario: Disarmed on boot
- **Given** the ESP32 has just booted
- **Then** `isArmed = false` and motors are at 1000

#### Scenario: Client disconnect in dangerous mode
- **Given** the firmware is in `SOUND` or `RC` mode
- **When** the iOS WebSocket disconnects
- **Then** motors stop and the firmware reverts to `IDLE`

#### Scenario: Telemetry timeout
- **Given** any active flight mode
- **When** the corresponding input watchdog fires (see firmware spec)
- **Then** motors are forced to 1000 before any further control runs

---

### Requirement: System SHALL Be Reproducible From a Clean Checkout
The project SHALL build and deploy from a clean clone with only the
documented steps in `CLAUDE.md`.

#### Scenario: ESP32 firmware
- **Given** PlatformIO is installed and `secrets.ini` is filled in
- **When** the user runs `pio run && pio upload` from the firmware dir
- **Then** the ESP32 boots, joins WiFi, and starts beaconing

#### Scenario: iOS app
- **Given** Xcode 15+ is installed and the device UDID is known
- **When** the user runs `./deploy.sh [UDID]` (or the xcodebuild command
  documented in `CLAUDE.md`)
- **Then** the app is built and installed on the connected iPhone
