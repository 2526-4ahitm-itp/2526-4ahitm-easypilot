# Spec: Drone Telemetry

## ADDED Requirements

### Requirement: System SHALL Monitor Real-time Attitude
The system SHALL capture and display drone attitude (Roll, Pitch, Yaw) in real-time with at least 10Hz frequency.
#### Scenario: ESP32 sends telemetry to iOS App
- **Given** the ESP32 is connected to the Flight Controller and Mac Relay
- **When** the drone changes its orientation
- **Then** the iOS App 3D model shall rotate accordingly with less than 200ms latency

### Requirement: System SHALL Track Battery Status
The system SHALL monitor and display LiPo battery voltage and alert the pilot when it drops below critical levels.
#### Scenario: Low battery warning
- **Given** the drone is flying and battery drops below 14.0V
- **When** the telemetry packet is received
- **Then** the iOS App battery indicator shall turn red
