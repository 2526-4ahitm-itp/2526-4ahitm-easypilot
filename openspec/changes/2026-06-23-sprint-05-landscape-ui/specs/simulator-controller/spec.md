# Spec Delta: Simulator & Controller Tab — Landscape & Touch-Aware Stabilization

## MODIFIED Requirements

### Requirement: System SHALL Provide a Virtual Joystick Component
The iOS app SHALL include a reusable `VirtualJoystick` SwiftUI view.

#### Scenario: Joystick drag tracking
- **Given** the user places a finger on the joystick pad
- **When** they drag within the circular boundary
- **Then** the thumb indicator follows within the pad radius, reporting normalised X/Y values in [-1, 1]
- **And** an `isTouching` binding is set to `true` for the duration of the gesture
- **And** when released, spring-centering axes return to (0, 0); the throttle Y axis holds its last position
- **And** `isTouching` is set to `false` on release

---

### Requirement: System SHALL Simulate Drone Physics Phone-Side
`DroneSimulator` (ObservableObject) SHALL integrate joystick inputs and SHALL only auto-level attitude when no stick is being touched.

#### Scenario: RATE mode while sticks touched
- **Given** the simulator is armed in RATE mode and `sticksTouched == true`
- **When** stick deflection is zero (finger resting at centre)
- **Then** roll and pitch attitude DO NOT drift back to zero; they hold the current angle (only angularDrag damps rates)

#### Scenario: RATE mode on stick release
- **Given** the simulator is armed in RATE mode and `sticksTouched` transitions to `false`
- **When** the physics tick fires
- **Then** roll and pitch drift toward 0 at 30°/s (gravity return)

#### Scenario: BALANCE mode while sticks touched
- **Given** the simulator is armed in BALANCE mode and `sticksTouched == true`
- **When** stick deflection is read
- **Then** the P-controller is bypassed; pitch and roll integrate from stick input as angular rates (same physics as RATE mode)

#### Scenario: BALANCE mode on stick release
- **Given** the simulator is armed in BALANCE mode and `sticksTouched == false`
- **When** the physics tick fires
- **Then** the P-controller levels the drone toward horizontal (target roll = 0, target pitch = 0)

---

### Requirement: System SHALL Display a Simulator Tab
A "Simulator" tab SHALL be present and its layout SHALL adapt to device orientation.

#### Scenario: Portrait layout (regular vertical size class)
- **Given** the device is in portrait orientation
- **Then** telemetry, mode selector, joysticks and arm button are stacked in a frosted bottom panel (existing Sprint 4 layout)

#### Scenario: Landscape layout (compact vertical size class)
- **Given** the device is in landscape orientation
- **Then** the 3D scene fills the entire screen
- **And** joystick pads float in the bottom-left and bottom-right corners as standalone frosted disks (no full-width slab behind them)
- **And** the telemetry strip is rendered as a compact pill in the top-left
- **And** the arm/disarm button floats centered at the bottom between the joysticks
- **And** the settings panel (expo / kP) slides in as a right-edge drawer when toggled, overlaying only the right portion of the screen
