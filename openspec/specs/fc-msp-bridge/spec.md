## Purpose

How the ESP32 talks to the Betaflight flight controller with the MultiWii Serial Protocol (MSP v1) over UART: which messages are polled, how motor values are pushed, and how broken frames are handled (FSD §5.4).

## Requirements

### Requirement: MSP v1 framing

The ESP32 SHALL send and parse MSP v1 frames (`$M<` / `$M>`, size, command, payload, XOR checksum over size, command and payload) (§5.4).

`status: implemented`

#### Scenario: Bad checksum
- **WHEN** a received frame's checksum does not match
- **THEN** the frame is discarded and `[MSP] Checksum error` is logged

### Requirement: Attitude and analog polling

The ESP32 SHALL request `MSP_ATTITUDE (108)` every 100 ms and `MSP_ANALOG (110)` every 500 ms (§5.4).

`status: implemented`

#### Scenario: Attitude decoded
- **WHEN** an `MSP_ATTITUDE` response arrives
- **THEN** roll and pitch (tenths of a degree) and yaw (degrees) update the telemetry state

### Requirement: Motor output via MSP_SET_MOTOR

The ESP32 SHALL push motor values with `MSP_SET_MOTOR (214)` as eight uint16 values whenever the mixer output changes; motors 5–8 SHALL stay at 1000 and values below 1000 SHALL be sent as 0 (§5.4, §4.2).

`status: implemented`

#### Scenario: Mixer update
- **WHEN** a flight mode changes m1–m4
- **THEN** one `MSP_SET_MOTOR` frame with the four clamped values is sent

### Requirement: Unit tests for the MSP parser

The MSP parser and command handling SHALL be covered by automated tests (§13).

`status: not-implemented`

#### Scenario: Parser tested on CI
- **WHEN** CI runs
- **THEN** tests feed valid and corrupted MSP frames into the parser and check the decoded values (no firmware tests exist yet)
