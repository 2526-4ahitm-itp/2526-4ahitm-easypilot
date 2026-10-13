## Purpose

The Algorithms tab of the iOS app (formerly „Control“): tune the parameters of the firmware modes, start them on the drone and keep parameter sets as named profiles (FSD §8.2, US-06).

## Requirements

### Requirement: Start firmware modes with parameters

The Algorithms tab SHALL let the user set `baseThrottle`, `kPRoll`, `kPPitch` and `maxPWM`, arm the drone and start BALANCE, MANUAL or SOUND with these values (§8.2, §6).

`status: implemented`

#### Scenario: Start balance
- **WHEN** the user arms and starts BALANCE with `baseThrottle = 1200`
- **THEN** `{"cmd":"START_BALANCE","baseThrottle":1200,...}` is sent

### Requirement: Sound Mode

The Algorithms tab SHALL offer Sound Mode: the phone's combined tilt `min(sqrt(pitch² + roll²), 90)` maps linearly to PWM 1000 at 0° and `maxPWM` (1050–1500) at 45° and above, sent as `TILT_SOUND` at 10 Hz; above 60° Sound Mode SHALL stop (§8.2, §7.2, US-02).

`status: implemented`

#### Scenario: Half tilt
- **WHEN** the tilt is 22.5° and `maxPWM` is 1400
- **THEN** the app sends `TILT_SOUND {pwm: 1200}`

#### Scenario: Beyond 45 degrees
- **WHEN** the tilt is 80° and `maxPWM` is 1400
- **THEN** the PWM stays at 1400

### Requirement: Stop button while a mode runs

The Algorithms tab SHALL show a STOP button whenever the firmware reports a mode other than IDLE (§8.2, §7.1).

`status: partial`

#### Scenario: RC mode running
- **WHEN** the firmware reports `"mode":"RC"`
- **THEN** the STOP button is visible (partial: RC is mapped to IDLE, so the button is hidden)

### Requirement: Control profiles

The app SHALL save, rename and delete named control profiles and keep them across restarts; saving a profile with an existing id SHALL replace it (§8.2, US-06).

`status: implemented`

#### Scenario: Restart
- **WHEN** a profile is saved and the app is restarted
- **THEN** the profile is listed with the same values

#### Scenario: Corrupt storage
- **WHEN** the stored profile data is not valid JSON
- **THEN** the app starts with an empty list instead of crashing
