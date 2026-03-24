# Spec: EasyPilot Core

## ADDED Requirements

### Requirement: System SHALL Provide 3D Drone Visualization
The system SHALL display a real-time 3D model of the drone that reflects its physical attitude.
#### Scenario: Load 3D model
- **Given** the iOS app is launched
- **When** the dashboard view appears
- **Then** the USDZ drone model shall be loaded and displayed in the SceneView

### Requirement: System SHALL Support WiFi Communication
The system SHALL establish a connection between the iPhone and the ESP32 via WiFi.
#### Scenario: Connect to drone
- **Given** the drone is powered and broadcasting its IP
- **When** the iOS app starts listening for UDP packets
- **Then** the connection status shall be updated to CONNECTED
