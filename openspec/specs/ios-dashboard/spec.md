## Purpose

The Dashboard tab of the iOS app: the pilot's live view of the drone with telemetry, a 3D model that follows the attitude, the phone's own tilt, the safe test and manual connection (FSD §8.1, US-01). Sound Mode lives in the Algorithms tab (see `ios-algorithms`).

## Requirements

### Requirement: Live telemetry display

The Dashboard SHALL show roll, pitch, yaw, the four motor values, voltage, battery percentage, armed state and flight mode from the latest telemetry frame (§8.1).

`status: implemented`

#### Scenario: Frame received
- **WHEN** a telemetry frame arrives
- **THEN** all values on the Dashboard update

### Requirement: Connection and data source indicator

The Dashboard SHALL show whether the app is connected and whether the data comes from a real FC (`fc=true`) or is simulated (§8.1, §7.2).

`status: implemented`

#### Scenario: Offline
- **WHEN** the WebSocket is not connected
- **THEN** the status shows offline in the danger colour

#### Scenario: Simulated data
- **WHEN** frames arrive with `"fc":false`
- **THEN** the Dashboard marks the data as not coming from the FC

### Requirement: 3D drone model

The Dashboard SHALL render the drone model (`drohne-compressed.usdz`) in a SceneKit view and rotate it with the telemetry attitude (§8.1, US-01).

`status: implemented`

#### Scenario: Attitude change
- **WHEN** roll changes by 20° in the telemetry
- **THEN** the model rolls by 20°

### Requirement: Phone tilt card

The Dashboard SHALL show the phone's own pitch and roll from CoreMotion, so the pilot sees what Sound Mode will use (§8.1).

`status: implemented`

#### Scenario: Phone tilted
- **WHEN** the phone is tilted forward
- **THEN** the pitch value on the card changes accordingly

### Requirement: Safe test

The Dashboard SHALL offer a safe test that sends `SAFE_TEST` (at most once every 2 s) and shows an overlay while it is active (§8.1, §5.2).

`status: implemented`

#### Scenario: Safe test triggered
- **WHEN** the safe test is activated
- **THEN** `SAFE_TEST` is sent and the overlay „SAFE TEST MODE ACTIVE“ is visible
