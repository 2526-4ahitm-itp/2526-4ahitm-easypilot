## Purpose

The telemetry contract between the ESP32 and the iOS app: a 10 Hz JSON frame with attitude, motors, battery and state, how the app decodes it, and how it behaves when the FC is offline (FSD §5.3, §7.2, §15, US-01).

## Requirements

### Requirement: 10 Hz telemetry frame

The ESP32 SHALL broadcast a JSON frame to every connected WebSocket client every 100 ms containing `roll, pitch, yaw, m1, m2, m3, m4, voltage, batteryPercentage, armed, mode, fc` (§5.3, §15).

`status: implemented`

#### Scenario: Frame content
- **WHEN** a client is connected
- **THEN** it receives a frame with all twelve fields at least 10 times per second

### Requirement: Tolerant decoding in the app

The app SHALL decode full frames as well as minimal frames from older firmware that only contain `roll, pitch, yaw`, ignore unknown fields, and reject frames without attitude (§5.3).

`status: implemented`

#### Scenario: Minimal frame
- **WHEN** `{"roll":0,"pitch":0,"yaw":0}` is decoded
- **THEN** decoding succeeds and all optional fields are nil

#### Scenario: Frame without attitude
- **WHEN** a frame without `roll`/`pitch`/`yaw` is decoded
- **THEN** decoding fails and the frame is dropped

### Requirement: Flight mode mapping

The app SHALL map the `mode` string to its flight mode enum and fall back to IDLE for unknown or missing values; every mode the firmware reports SHALL map to a real case (§5.3, §6).

`status: partial`

#### Scenario: Unknown mode
- **WHEN** `mode` is missing or `"foo"`
- **THEN** the app shows IDLE and does not crash

#### Scenario: RC mode reported
- **WHEN** the firmware reports `"mode":"RC"`
- **THEN** the app shows RC (partial: it currently maps to IDLE, and the Algorithms tab hides its STOP button)

### Requirement: Simulated telemetry when the FC is offline

When no valid MSP answer arrives for 2 s and the drone is not armed, the firmware SHALL set `fc=false` and generate simulated telemetry so the dashboard stays usable for demos (§7.2).

`status: implemented`

#### Scenario: FC unplugged
- **WHEN** the FC is silent for 2 s while disarmed
- **THEN** frames continue with `"fc":false` and simulated attitude

### Requirement: Low battery warning

The app SHALL show the battery in a warning colour when the voltage drops below 14.0 V (§4.3, §8.1).

`status: implemented`

#### Scenario: Critical voltage
- **WHEN** a frame with `voltage` below 14.0 arrives
- **THEN** the battery indicator turns red

### Requirement: End-to-end latency

A change of the drone's attitude SHALL be visible in the app in under 200 ms (§15, US-01).

`status: partial`

#### Scenario: Latency measured
- **WHEN** the drone is tilted by hand
- **THEN** the 3D model follows in under 200 ms (partial: met by design at 10 Hz, but never measured with the real drone and no longer measurable since the Air Unit defect)
