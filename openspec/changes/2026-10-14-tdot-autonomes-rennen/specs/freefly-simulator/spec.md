## ADDED Requirements

### Requirement: Own free-flight simulator

The project SHALL provide its own free-flight simulator (`simulator/autopilot/freefly`) with an FPV camera, a village world with obstacles and gate tracks, flown with the calibrated controller or the keyboard, independent of Liftoff (§20.7, §1.2).

`status: implemented`

#### Scenario: Flying without Liftoff
- **WHEN** a user starts `python -m autopilot.freefly`
- **THEN** the simulator opens in its menu and the drone can be flown in acro mode with the controller or the keyboard

### Requirement: Selectable physics models

The simulator SHALL offer three physics models with the same interface: "Klassisch" (`sim.py`), "Liftoff-nah" fitted to recorded Liftoff telemetry (`physics.py`, default) and "Realistisch", a 5-inch racing drone with motor, Betaflight-controller, aerodynamics, battery and wind models (`physics_real.py`) (§20.7).

`status: implemented`

#### Scenario: Realistic physics with wind
- **WHEN** the user selects physics "Realistisch" and wind "leicht"
- **THEN** the drone is simulated with the realistic model and gusty wind, and the OSD shows the battery voltage

### Requirement: Tracks with difficulty levels

The simulator SHALL provide five gate tracks of increasing difficulty in the same world (`anfaenger`, `dorfrunde`, `scheunen`, `turm`, `profi`), selectable in the menu or with `--strecke` (§20.7).

`status: implemented`

#### Scenario: Track change
- **WHEN** the user selects the track "profi"
- **THEN** the gates of that track replace the current ones and obstacles blocking them are removed

### Requirement: Autopilots in the own simulator

The simulator SHALL let the EasyPilot autopilot fly its tracks with the same racing line and race controller as in Liftoff, by track data or by camera only, and SHALL offer a neural-network pilot that can keep learning from its own flights (§20.3, §20.7).

`status: implemented`

#### Scenario: Race controller in the own simulator
- **WHEN** the autopilot is started on a track of the simulator
- **THEN** it flies the racing line through all gates with the race controller used for Liftoff

#### Scenario: Watching the network learn
- **WHEN** the operator starts the AI showcase "Lernen zuschauen"
- **THEN** the network flies attempts with exploration noise, the flights are recorded and a background learner improves the model between attempts

### Requirement: Game modes for visitors

The simulator SHALL offer game modes for humans: race with a ghost of the best lap, rings, parcel delivery and freestyle, each with its own best results (§20.5, §20.7).

`status: implemented`

#### Scenario: Ghost of the best lap
- **WHEN** a visitor flies a track that already has a best lap
- **THEN** the best lap flies along as a ghost and the OSD shows the time difference at every gate

### Requirement: Remote control from EasyPilot Studio

The simulator SHALL accept commands from EasyPilot Studio as JSON lines over a local TCP socket (settings, prepare, go, stop, messages, window layout, quit) and SHALL report run results back, so that Studio can run the open-day flow and leaderboards with the own simulator as an alternative to Liftoff (§20.5, §20.7).

`status: implemented`

#### Scenario: Run started from Studio
- **WHEN** Studio sends `prepare` and then `go` with the autopilot enabled
- **THEN** the drone starts from the start pad, the autopilot flies and the result is sent back to Studio
