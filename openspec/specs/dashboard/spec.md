# Spec: iOS Dashboard

The Dashboard tab is the iOS app's "live view" of the drone — it shows
telemetry, lets the user see the drone's attitude in 3D, and exposes the
small handful of buttons a pilot needs without leaving the field.

It is **not** the simulator (see `simulator-controller/spec.md`) and it
is **not** the algorithm-tuning UI (formerly the "Control" tab, now
"Algorithms"). Those are separate tabs.

## ADDED Requirements

### Requirement: System SHALL Display Live Telemetry
The Dashboard SHALL display the same telemetry fields the ESP32
broadcasts at 10 Hz.

#### Scenario: Telemetry cards
- **Given** an active WebSocket connection
- **Then** the dashboard renders cards/values for: roll (°), pitch (°),
  yaw (°), four motor PWM values, battery voltage, battery percentage,
  armed state, and current flight mode

#### Scenario: Connection state
- **Given** the WebSocket is not connected
- **Then** the dashboard shows a `DISCONNECTED` badge
- **And** when it is connected, a `PulsingDot` shows live status

---

### Requirement: System SHALL Render a 3D Drone Model
The dashboard SHALL include a SceneKit view that mirrors the drone's
attitude in real time.

#### Scenario: Attitude reflects telemetry
- **Given** the WebSocket is delivering telemetry
- **When** roll, pitch, or yaw change
- **Then** the 3D drone model rotates to match within 200 ms

#### Scenario: Offline state
- **Given** there is no telemetry
- **Then** the model remains in its last known attitude (no jitter, no
  reset to zero)

---

### Requirement: System SHALL Show iPhone Tilt Card
The dashboard SHALL include an "iPhone motion" card driven by
`MotionManager` so the pilot can see what the phone's own sensors are
reading.

#### Scenario: Tilt update rate
- **Given** the dashboard is visible
- **Then** the card updates at 10 Hz with the iPhone's pitch and roll
  in degrees (from CoreMotion)

#### Scenario: Safe-test trigger
- **Given** the connection is `LOCAL` (iOS detected ESP32 on same /24)
- **When** the user holds the dashboard's "Safe Test" button (or
  triggers the tilt-based variant from Sprint 3)
- **Then** the app sends `SAFE_TEST` over the local channel and the
  ESP32 spins M1 at 1050 PWM for 500 ms

---

### Requirement: System SHALL Support Sound Mode
The dashboard SHALL include a Sound Mode that maps iPhone tilt angle to
all-motor PWM.

#### Scenario: Tilt-to-PWM mapping
- **Given** Sound Mode is active and armed
- **When** the iPhone tilt angle = `sqrt(pitch² + roll²)` is computed
- **Then** PWM = `1000 + Int((min(tiltAngle, 45°) / 45°) × (maxSoundPWM
  − 1000))`
- **And** the iOS app sends `TILT_SOUND` at 10 Hz with that PWM

#### Scenario: Emergency cut-off
- **Given** Sound Mode is active
- **When** tilt angle exceeds 60°
- **Then** the iOS app sends `STOP` and disarms

#### Scenario: ESP32-side timeout
- **Given** Sound Mode is active on the firmware
- **When** no `TILT_SOUND` packet arrives for 1 s
- **Then** all motors are forced to 1000 (specified in `firmware/spec.md`)

---

### Requirement: System SHALL Allow Manual IP Entry
The dashboard SHALL provide a text field for entering the ESP32 IP
manually when UDP discovery is unavailable.

#### Scenario: Manual override
- **Given** the user enters an IP and taps Connect
- **Then** the app reconnects the WebSocket to that IP
- **And** the manual IP persists across app launches

---

### Requirement: System SHALL Support MSP-Backed Telemetry From a Betaflight FC
The dashboard SHALL surface whether the ESP32 is reading from a real
Betaflight FC or from its simulation mode.

#### Scenario: FC indicator
- **Given** the telemetry frame contains `"fc": true`
- **Then** the dashboard shows an `FC` badge or similar indicator
- **And** when `"fc": false`, the dashboard shows that telemetry is
  simulated (so the pilot does not mistake demo data for live data)
