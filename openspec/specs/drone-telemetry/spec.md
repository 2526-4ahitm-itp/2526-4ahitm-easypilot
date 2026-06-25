# Spec: Drone Telemetry

## ADDED Requirements

### Requirement: System SHALL Monitor Real-time Attitude
The system SHALL capture and display drone attitude (Roll, Pitch, Yaw) in real-time with at least 10Hz frequency.
#### Scenario: ESP32 sends telemetry over the local path
- **Given** the iPhone and ESP32 are on the same WiFi subnet
- **When** the drone changes its orientation
- **Then** the ESP32 broadcasts telemetry directly via UDP on port 4242 and the iOS App 3D model rotates with less than 200ms latency

#### Scenario: ESP32 sends telemetry over the remote relay path
- **Given** the iPhone is not on the same subnet as the ESP32
- **When** the drone changes its orientation
- **Then** the ESP32 forwards telemetry to the Mac/Mac-Mini Python relay over WebSocket and the relay (exposed via Ngrok) delivers it to the iOS App, which displays a `RELAY` badge

### Requirement: System SHALL Track Battery Status *(Deferred)*
The system SHALL monitor and display LiPo battery voltage and alert the pilot when it drops below critical levels.

> **Status: deferred.** Originally scoped under the archived `sprint-02`; not yet
> implemented. Kept here to preserve intent for a future sprint.

#### Scenario: Low battery warning
- **Given** the drone is flying and battery drops below 14.0V
- **When** the telemetry packet is received
- **Then** the iOS App battery indicator shall turn red
