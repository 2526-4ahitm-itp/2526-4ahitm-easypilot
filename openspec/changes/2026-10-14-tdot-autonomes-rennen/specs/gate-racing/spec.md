## ADDED Requirements

### Requirement: Gate positions from the track file

The autopilot SHALL read gate centre, normal, width and height for every gate of a Liftoff track (official tracks from the game bundles or custom tracks), in race order (§20.2).

`status: implemented`

#### Scenario: Custom track loaded
- **WHEN** the autopilot loads the track built for the open day
- **THEN** it lists every gate with its pose and size in the order of the race

#### Scenario: Track file not readable
- **WHEN** the track file does not contain gate poses
- **THEN** gate poses can be recorded once by flying through each gate and are stored for later runs

### Requirement: Gates detected in the camera image

The autopilot SHALL detect gates in the captured Liftoff FPV image, estimate each gate's pose from its four inner corners and the known gate size, and fuse it with the track file (§20.2, US-14).

`status: implemented`

#### Scenario: Gate moved
- **WHEN** a gate is placed 1 m away from its position in the track file
- **THEN** the racing line follows the detected position and the drone passes through the gate

#### Scenario: Live overlay
- **WHEN** the autopilot is flying
- **THEN** detected gates are framed on screen at 30 fps or more

### Requirement: Racing line through all gates

The autopilot SHALL plan a smooth trajectory through all gates in order, crossing each gate along its normal, with a speed profile limited by the measured thrust and the allowed lateral acceleration (§20.3).

`status: implemented`

#### Scenario: Speed scaling
- **WHEN** `aggressiveness` is raised from 0.5 to 1.0
- **THEN** the planned lap time decreases and the planned path still passes through every gate centre within the safety margin

### Requirement: Full-speed trajectory tracking

The autopilot SHALL follow the racing line at full speed using full attitude control (no fixed tilt limit) and the identified rate and thrust curves of the Liftoff drone (§20.3, US-11).

`status: partial`

#### Scenario: Ten laps at full speed
- **WHEN** the autopilot flies 10 laps with `aggressiveness = 1.0`
- **THEN** it passes every gate, does not crash, and its best lap is faster than the team's best lap with a controller

### Requirement: Lap timing through gate crossings

The autopilot SHALL count a gate when the drone's path between two telemetry samples crosses the gate plane inside the gate frame, and time laps with Liftoff's telemetry timestamps (§20.3, §20.5).

`status: implemented`

#### Scenario: Missed gate
- **WHEN** the drone passes beside a gate instead of through it
- **THEN** the gate is not counted and the lap is marked invalid
