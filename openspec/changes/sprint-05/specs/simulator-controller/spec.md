## ADDED Requirements

### Requirement: System SHALL Render the Simulator Tab in Landscape Orientation
The `SimulatorView` SHALL provide a dedicated layout for landscape (horizontal) device orientation that keeps both joystick pads, the telemetry strip, and the header simultaneously visible without overflow.

#### Scenario: Landscape detection
- **WHEN** the simulator tab is visible and the SwiftUI canvas reports a width greater than its height
- **THEN** the simulator renders its landscape layout branch
- **AND** when the canvas reports height greater than width, the simulator renders its portrait layout branch (unchanged from prior behaviour)

#### Scenario: Landscape layout arrangement
- **WHEN** the landscape layout branch is active
- **THEN** the left joystick (`THR/YAW`) is anchored to the left side of the screen with an inset of at least 16 pt
- **AND** the right joystick (`PCH/ROL`) is anchored to the right side of the screen with an inset of at least 16 pt
- **AND** the horizon indicator, roll/pitch/yaw values, and four motor bars are arranged in the centre column between the joysticks
- **AND** the header (armed state, flight-mode toggle, sim/live mode pill) occupies a single strip across the top of the screen no taller than 40 pt

#### Scenario: Rotation during use preserves simulation state
- **WHEN** the user rotates the device while the simulator is armed and running
- **THEN** the `DroneSimulator` `_roll`, `_pitch`, `_yaw`, motor PWM values, and armed state are unchanged across the layout switch
- **AND** the only observable changes are layout-related (positions of joysticks, telemetry strip, header)

#### Scenario: Portrait behaviour is preserved
- **WHEN** the device is held in portrait orientation
- **THEN** the simulator's layout, control positions, and visual styling match the prior portrait behaviour
- **AND** no functional regression is introduced for portrait users

---

### Requirement: System SHALL Expose Joystick Touch Activity
The `VirtualJoystick` component SHALL publish whether a thumb is currently touching the pad, independent of the stick's deflection.

#### Scenario: Active flag follows touch lifecycle
- **WHEN** the user places a finger on the joystick pad
- **THEN** the joystick's `isActive` binding is set to `true`
- **AND** when the finger lifts, `isActive` is set to `false`

#### Scenario: Active flag distinguishes thumb-at-centre from no thumb
- **WHEN** the user holds a thumb exactly at the centre of the pad (stick output `(0, 0)`)
- **THEN** `isActive` reports `true`
- **AND** when no thumb is on the pad and stick output is `(0, 0)` due to spring-centering, `isActive` reports `false`

#### Scenario: Backward compatibility
- **WHEN** a caller constructs `VirtualJoystick` without supplying an `isActive` binding
- **THEN** the joystick still functions and the touch lifecycle is tracked internally without requiring the caller to observe it

---

### Requirement: System SHALL Auto-Stabilize the Simulator on Right-Stick Release
When the user is not touching the right (attitude) joystick AND the simulator is armed AND throttle exceeds 0.05, the simulator SHALL actively drive roll and pitch toward 0° rather than relying only on rate-mode passive drift.

#### Scenario: Active level-target in rate mode with no thumb on right stick
- **WHEN** the simulator is in rate-mode flight, armed, throttle > 0.05, and the right joystick's `isActive` binding reports `false`
- **THEN** the simulator drives `_roll` and `_pitch` toward 0° using the same P-controller used in balance mode (with `kPRoll`, `kPPitch`, `kPScale`)
- **AND** convergence to within ±1° of level completes in ≤ 1.5 s from a 30° starting attitude

#### Scenario: Balance mode unchanged with no thumb on right stick
- **WHEN** the simulator is in balance-mode flight and the right joystick's `isActive` reports `false`
- **THEN** the existing balance-mode P-controller continues to drive toward target `(0°, 0°)` — behaviour is unchanged from the prior spec

#### Scenario: Thumb on right stick suppresses auto-stabilize
- **WHEN** the right joystick's `isActive` reports `true` (including a thumb held at the exact centre)
- **THEN** auto-stabilize does not run
- **AND** the simulator behaves per its current flight mode (rate or balance) using the stick's reported values

#### Scenario: Disarmed or low throttle does not invoke auto-stabilize
- **WHEN** the simulator is disarmed OR throttle ≤ 0.05
- **THEN** auto-stabilize does not run regardless of `isActive`
- **AND** the prior disarmed/low-throttle behaviour (gravity-return drift to 0°, motors at 1000 PWM) is preserved

---

## MODIFIED Requirements

### Requirement: System SHALL Display a Simulator Tab
A new "Simulator" tab SHALL be added to the app's `TabView`.

#### Scenario: Layout (portrait)
- **WHEN** the Simulator tab is active and the device is in portrait orientation
- **THEN** the screen shows: header (mode toggle, armed state), joystick area (two pads), and a telemetry strip (horizon indicator, roll/pitch/yaw values, four motor bars)

#### Scenario: Sim / Live mode placeholder
- **WHEN** the user taps the "Live" segment of the sim/live mode pill
- **THEN** a tooltip/label reads "Available in a future sprint" and the toggle snaps back to Simulator

#### Scenario: Arm / Disarm
- **WHEN** the user taps "Arm Simulator" while disarmed
- **THEN** the simulator arms and physics begin
- **AND** no WebSocket command is sent
