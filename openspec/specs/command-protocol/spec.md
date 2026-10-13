## Purpose

The command vocabulary the iOS app sends to the ESP32 over the WebSocket on port 81: JSON objects with a `cmd` field plus two plain-text shortcuts (FSD §5.2). The exact wire format is pinned by the iOS unit tests (`DroneCommandTests`) so app and firmware cannot drift apart.

## Requirements

### Requirement: One WebSocket for commands

The app SHALL send every command as a single WebSocket TEXT frame to `ws://<esp32>:81`, on the same connection that carries telemetry (§5.2).

`status: implemented`

#### Scenario: Command sent
- **WHEN** the app sends a command while connected
- **THEN** exactly one TEXT frame with the command body is written to the socket

### Requirement: Supported command set

The firmware SHALL honour `ARM`, `DISARM`, `STOP`, `START_BALANCE {baseThrottle,kPRoll,kPPitch}`, `START_MANUAL {roll,pitch,yaw,m1..m4,voltage,batteryPercentage}`, `START_SOUND {maxPWM}`, `TILT_SOUND {pwm}`, `START_RC {kPRoll,kPPitch}`, `RC {thr,pit,rol,yaw}` and the plain-text commands `SAFE_TEST` and `SIMULATE` (§5.2, §6).

`status: implemented`

#### Scenario: Arm
- **WHEN** `{"cmd":"ARM"}` is received
- **THEN** the drone is armed and the next telemetry frame reports `"armed":true`

#### Scenario: Disarm
- **WHEN** `{"cmd":"DISARM"}` is received
- **THEN** the drone is disarmed, the mode becomes IDLE and the motors stop

#### Scenario: Safe test
- **WHEN** `SAFE_TEST` is received while armed
- **THEN** motor M1 runs at 1050 for 500 ms

#### Scenario: Start command while disarmed
- **WHEN** any `START_*` command arrives while the drone is not armed
- **THEN** it is ignored and the firmware logs `Not armed`

### Requirement: Locale-independent number format

The app SHALL encode decimal numbers with a dot and two decimals regardless of the phone's region, because ArduinoJson only parses `.` (§5.2).

`status: implemented`

#### Scenario: Austrian region
- **WHEN** `START_BALANCE` with `kPRoll = 1.5` is built on a phone set to region Austria
- **THEN** the payload contains `1.50`, not `1,50`

### Requirement: Typed command builder in the app

The app SHALL build commands through the `DroneCommand` type instead of hand-written strings in views (§5.2).

`status: partial`

#### Scenario: Views use DroneCommand
- **WHEN** a view sends a command
- **THEN** it uses `DroneCommand.payload` (partial: `SimulatorView` still builds `START_RC`/`RC`/`DISARM` strings by hand; `RC` commands are missing from the enum)
