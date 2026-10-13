## Purpose

The phase 2 prototype in `simulator/liftoff-hover`: a Python middleware between the pilot's radio and the FPV simulator Liftoff. It passes the sticks through a virtual joystick (vJoy) and, on a button press, flies the drone itself with the help of Liftoff's UDP telemetry to brake and hold position, height and heading — DJI-style hover (FSD §1.2, §11, US-07). Liftoff provides the physics; the control algorithms are meant to be reused by the web simulator.

## Requirements

### Requirement: Pass-through via vJoy

The middleware SHALL read the physical radio with pygame and write the sticks to vJoy device 1 in a fixed layout (X roll, Y pitch, Z throttle, RX yaw), normalised with the calibrated centre and range of each axis (§11).

`status: implemented`

#### Scenario: Off-centre axis
- **WHEN** the calibrated pitch centre is 0.05 and the raw value is 0.05
- **THEN** vJoy pitch is 0

### Requirement: Calibration wizard

`hover.py calibrate` SHALL detect the throttle, yaw, pitch and roll axes, their direction and the hover button from guided stick movements and store them in `config.json` (§11).

`status: implemented`

#### Scenario: Throttle detected
- **WHEN** the user moves the throttle up when asked
- **THEN** the axis with the largest change is stored as throttle with its low and high value

### Requirement: Telemetry and attitude conventions

The middleware SHALL read Liftoff's UDP telemetry (timestamp, position, quaternion, gyro, input) and derive velocity, pitch (+ nose down), roll (+ right side down), yaw (+ turning right) and tilt from Unity's left-handed, Y-up frame; a position jump over 5 m SHALL count as reset (§11).

`status: implemented`

#### Scenario: Respawn
- **WHEN** the position jumps by 50 m between two packets
- **THEN** the reset flag is set and hover switches off

### Requirement: Hover on button press

On the hover button the middleware SHALL brake the drone, lock position, height and heading once it has slowed down, and hold them with cascaded controllers at 250 Hz; an integral on the climb rate error SHALL correct a wrong hover throttle estimate (§11, §15, US-07).

`status: implemented`

#### Scenario: Engaged while climbing
- **WHEN** hover is switched on while climbing at 16 m/s
- **THEN** the drone is stopped after about 2 s and holds its position and height (measured in Liftoff on 2026-09-28)

#### Scenario: Wrong hover throttle
- **WHEN** the learned hover throttle is 0.30 but the drone needs 0.45
- **THEN** the height settles within 0.2 m (closed-loop test)

### Requirement: Smooth hand-over to the pilot

Pressing the button again SHALL return control to the pilot with a 0.5 s blend; losing telemetry or a reset SHALL switch to manual immediately (§11).

`status: implemented`

#### Scenario: Telemetry lost
- **WHEN** no telemetry arrives for 250 ms during hover
- **THEN** the middleware switches to manual

### Requirement: Automated tests

The controller SHALL be covered by closed-loop tests that run in CI (§13).

`status: implemented`

#### Scenario: CI run
- **WHEN** the Simulator workflow runs
- **THEN** `test_hover.py` checks braking, holding, wrong hover throttle, stick limits and attitude conventions
