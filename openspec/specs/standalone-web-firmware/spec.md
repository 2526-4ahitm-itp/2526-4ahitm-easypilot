## Purpose

The second firmware `PlatformIO/Projects/easypilot`: it serves its own web dashboard on port 80, runs a take-off and hover state machine with a PID loop and supports OTA updates. It is used for tethered desk tests and demos without the phone (FSD §9).

## Requirements

### Requirement: Self-hosted control page

The firmware SHALL serve a control page on HTTP port 80 with start buttons for a time-based and an accelerometer-based take-off and a live state display (§9).

`status: implemented`

#### Scenario: Open dashboard
- **WHEN** a browser opens `http://<esp32>/`
- **THEN** the control page with both start buttons is shown

### Requirement: Level check before take-off

A start via `/start_time` or `/start_acc` SHALL be refused with HTTP 400 when roll or pitch exceed 5° (§7.2, §9).

`status: implemented`

#### Scenario: Tilted drone
- **WHEN** a start is requested with roll = 8°
- **THEN** the firmware answers 400 and does not start

### Requirement: Heartbeat and crash watchdogs

The page SHALL send `/heartbeat` every 500 ms; the firmware SHALL enter FAILSAFE (`drone_state = -1`) after 1.5 s without heartbeat and CRASH (`drone_state = -2`) when roll or pitch exceed 60°, stopping the motors in both cases (§7.2).

`status: implemented`

#### Scenario: Crash
- **WHEN** the drone tips over past 60° while flying
- **THEN** `drone_state = -2` and all motors stop

### Requirement: Throttle ceiling

Motor values SHALL be clamped to 1000–`MAX_THROTTLE` with `MAX_THROTTLE = 1400` (§4.2).

`status: implemented`

#### Scenario: Controller asks for more
- **WHEN** the PID output exceeds 1400
- **THEN** 1400 is sent

### Requirement: OTA updates

The firmware SHALL accept password-protected OTA updates under the hostname `ESP32-Drohne` and reset the flight state before flashing (§9).

`status: implemented`

#### Scenario: OTA start
- **WHEN** an OTA upload starts
- **THEN** the motors stop and the controller state is reset before writing
