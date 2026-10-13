## Purpose

The Simulator tab of the iOS app: a phone-side drone physics simulation with virtual joysticks, three flight modes and a SceneKit world, for practising without the real drone (FSD §8.3, US-04). Built in sprints 4 and 5.

## Requirements

### Requirement: Virtual joysticks

The app SHALL provide two virtual joysticks in Mode 2 layout that report normalised values in [-1, 1]; the right stick and the yaw axis SHALL spring back to centre while the throttle axis keeps its position, and an expo curve `out = r³·E + r·(1−E)` (default E = 0.35) SHALL apply to roll, pitch and yaw (§8.3).

`status: implemented`

#### Scenario: Release
- **WHEN** the finger is lifted from the right stick
- **THEN** pitch and roll return to 0 and throttle keeps its value

### Requirement: Phone-side physics

`DroneSimulator` SHALL integrate thrust, gravity and drag with rate-mode attitude control, and SHALL hold altitude with a PID that compensates tilt (`1/(cos pitch · cos roll)`) (§8.3).

`status: implemented`

#### Scenario: Hover at mid throttle
- **WHEN** the simulator is armed and the throttle stick is released at mid position
- **THEN** the drone holds its altitude

### Requirement: Flight modes RATE, BALANCE and POSHOLD

The simulator SHALL offer RATE (attitude holds while a stick is touched, levels on release), BALANCE (P-controller levels the drone when the right stick is released) and POSHOLD (captures the position on release and flies back to it with limited tilt) (§8.3, US-04).

`status: implemented`

#### Scenario: POSHOLD release
- **WHEN** POSHOLD is active and the right stick is released while moving
- **THEN** the drone brakes by counter-tilting (max 14°) and returns to the captured position

### Requirement: Stabilisation only without touch

Auto-levelling SHALL only act while no finger is on the right stick, and the joystick SHALL turn green while stabilisation is active (§8.3).

`status: implemented`

#### Scenario: Finger resting at centre
- **WHEN** a finger rests on the right stick at centre in BALANCE
- **THEN** the controller does not level the drone

### Requirement: Portrait and landscape layout

The Simulator tab SHALL adapt to orientation: in landscape the 3D scene fills the screen, the joysticks float in the bottom corners and the settings slide in from the right (§8.3).

`status: implemented`

#### Scenario: Rotate phone
- **WHEN** the phone is rotated to landscape
- **THEN** the joysticks move to the bottom corners over the full-screen scene
