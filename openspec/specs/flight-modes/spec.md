## Purpose

The flight modes of the companion firmware `PlatformIO/Projects/EasyPilotIOS`: IDLE, BALANCE, MANUAL, SOUND and RC, how each one is entered and how motor values are mixed (FSD §6). Motor layout: M1 front-left, M2 front-right, M3 rear-left, M4 rear-right.

## Requirements

### Requirement: IDLE as default mode

The firmware SHALL boot into IDLE with all motors at 1000 and return to IDLE on `DISARM` and `STOP` (§6, §7.1).

`status: implemented`

#### Scenario: Boot
- **WHEN** the ESP32 boots
- **THEN** the mode is IDLE, the drone is disarmed and m1–m4 are 1000

### Requirement: BALANCE mode

On `START_BALANCE` while armed, the firmware SHALL run a P-controller on roll and pitch around `baseThrottle` with gains `kPRoll` and `kPPitch` (§6).

`status: implemented`

#### Scenario: Roll error corrected
- **WHEN** BALANCE is active and the measured roll is not 0
- **THEN** `rAdj = kPRoll × (0 − roll)` is added to M1/M3 and subtracted from M2/M4, and `pAdj = kPPitch × (0 − pitch)` is subtracted from M1/M2 and added to M3/M4, each clamped to 1000–2000

### Requirement: MANUAL mode

On `START_MANUAL` while armed, the firmware SHALL take attitude, motor, voltage and battery values from the client and report them as telemetry (§6).

`status: implemented`

#### Scenario: Client values applied
- **WHEN** `START_MANUAL` with `m1 = 1200` arrives while armed
- **THEN** the next telemetry frame reports `m1 = 1200` and mode MANUAL

### Requirement: SOUND mode

On `START_SOUND` while armed, the firmware SHALL clamp `maxPWM` to 1000–1500 and drive all four motors with the PWM from the latest `TILT_SOUND` packet, clamped to `maxPWM` (§6, US-02).

`status: implemented`

#### Scenario: Tilt packet
- **WHEN** SOUND is active with `maxPWM = 1400` and `TILT_SOUND {pwm: 1600}` arrives
- **THEN** all motors run at 1400

### Requirement: RC mode

On `START_RC` while armed, the firmware SHALL take throttle (1000–2000), target pitch and roll (±45°) and a yaw adjustment (±100) from `RC` packets and stabilise towards the target angles with the BALANCE P-controller plus yaw mixing (§6, §8.4, US-05).

`status: implemented`

#### Scenario: Target angle
- **WHEN** RC is active and an `RC` packet with `pit = 10` arrives
- **THEN** the controller drives the measured pitch towards 10°

#### Scenario: RC packet outside RC mode
- **WHEN** an `RC` packet arrives while the mode is not RC
- **THEN** it is ignored
