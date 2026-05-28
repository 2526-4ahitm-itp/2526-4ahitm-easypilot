# Spec: Simulator & Controller Tab

## ADDED Requirements

### Requirement: System SHALL Provide a Virtual Joystick Component
The iOS app SHALL include a reusable `VirtualJoystick` SwiftUI view.
#### Scenario: Joystick drag tracking
- **Given** the user places a finger on the joystick pad
- **When** they drag within the circular boundary
- **Then** the thumb indicator follows within the pad radius, reporting normalised X/Y values in [-1, 1]
- **And** when released, spring-centering axes return to (0, 0); the throttle Y axis holds its last position

#### Scenario: Expo curve
- **Given** an expo factor E ∈ [0, 1] (default 0.35)
- **When** raw stick value r is read
- **Then** the output is: `out = r³ · E + r · (1–E)`
- **And** this curve is applied per-axis on roll, pitch, yaw (not throttle)

---

### Requirement: System SHALL Simulate Drone Physics Phone-Side
`DroneSimulator` (ObservableObject) SHALL integrate joystick inputs at 20 Hz.
#### Scenario: Rate-mode attitude integration
- **Given** the simulator is armed and throttle > 0.05
- **When** a stick deflection is input
- **Then** `pitch += pitchRate · dt` where `pitchRate = expoOut · maxPitchRate`
- **And** roll and yaw integrate equivalently
- **And** attitude is clamped to ±85° (pitch/roll) to prevent gimbal lock

#### Scenario: Motor mixing
- **Given** current throttle T ∈ [0, 1] and attitude pitch/roll
- **When** motor PWM is computed
- **Then** base = 1000 + T · 600 (range 1000–1600)
- **And** small mixing deltas are added per motor for visual realism
- **And** all motor values are clamped to [1000, 2000]

#### Scenario: Disarmed / low throttle
- **Given** the simulator is disarmed OR throttle ≤ 0.05
- **When** the physics tick fires
- **Then** roll and pitch drift toward 0 at 20°/s (gravity return)
- **And** all motor PWM is set to 1000

---

### Requirement: System SHALL Display a Simulator Tab
A new "Simulator" tab SHALL be added to the app's `TabView`.
#### Scenario: Layout
- **Given** the Simulator tab is active
- **Then** the screen shows: header (mode toggle, armed state), joystick area (two pads), and a telemetry strip (horizon indicator, roll/pitch/yaw values, four motor bars)

#### Scenario: Sim / Live mode toggle
- **Given** the user taps the "Live" segment of the mode pill
- **Then** a tooltip/label reads "Available in Sprint 5" and the toggle snaps back to Simulator

#### Scenario: Arm / Disarm
- **Given** the simulator is disarmed
- **When** the user taps "Arm Simulator"
- **Then** the simulator arms and physics begin
- **And** no WebSocket command is sent

---

### Requirement: System SHALL Rename the Control Tab
The "Control" tab SHALL be labelled "Algorithms" with a matching SF Symbol.
