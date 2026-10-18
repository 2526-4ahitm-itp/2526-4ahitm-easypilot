## ADDED Requirements

### Requirement: Human versus program race flow

The race mode SHALL let a visitor fly the track with the controller (pass-through, timed by gate crossings) and then let the autopilot fly the same track with the same drone, switching modes with one key (§20.5, US-12).

`status: not-implemented`

#### Scenario: One round of the event
- **WHEN** a visitor finishes a lap and the operator switches to program mode
- **THEN** the autopilot flies the same track and both times are shown

### Requirement: Leaderboard

The race mode SHALL show a leaderboard on a second screen with nickname, lap time and rank, with the program's time as reference, and SHALL delete the entries after the event (§20.5, US-12).

`status: not-implemented`

#### Scenario: New best time
- **WHEN** a visitor beats the program's time
- **THEN** the visitor is listed above the program

### Requirement: Fast reset between runs

The race mode SHALL reset the drone through a vJoy button mapped to Liftoff's reset, so that one run can follow the next within 30 s (§20.5).

`status: implemented`

#### Scenario: Crash during a run
- **WHEN** a visitor crashes
- **THEN** the operator resets with one key and the run is marked invalid
