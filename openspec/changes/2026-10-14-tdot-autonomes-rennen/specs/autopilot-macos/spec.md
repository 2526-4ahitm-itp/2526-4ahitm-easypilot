## ADDED Requirements

### Requirement: Liftoff autopilot on macOS

The Liftoff autopilot and EasyPilot Studio SHALL run on macOS (Apple Silicon) with Liftoff from Steam, exchanging only the operating-system bindings: virtual gamepad through OpenJoystickDriver instead of vJoy, window handling through Quartz/AppKit, screen capture through mss and the Liftoff data folder under `~/Library/Application Support` (§20.7).

`status: implemented`

#### Scenario: Autopilot flies Liftoff on a Mac
- **WHEN** `ojdpad.py` is running and the autopilot is started on a Mac
- **THEN** Liftoff receives the stick values from the virtual gamepad and the autopilot reads the telemetry over UDP as on Windows

### Requirement: Safe virtual gamepad on macOS

The macOS gamepad bridge SHALL set throttle to zero and the sticks to centre when no stick packet arrives for 0.5 s (§20.7, §15).

`status: implemented`

#### Scenario: Autopilot stops sending
- **WHEN** the autopilot process ends without releasing the gamepad
- **THEN** after 0.5 s the gamepad reports zero throttle and centred sticks

### Requirement: One-click start on the presentation Mac

The project SHALL provide setup and double-click start scripts for the presentation Mac (`simulator/mac/`), including a kiosk exit and the detection of the connected controller (§20.5, §20.7).

`status: implemented`

#### Scenario: Starting the presentation
- **WHEN** the operator double-clicks `Start-EasyPilot.command`
- **THEN** the gamepad bridge, Liftoff and Studio start in their windows
