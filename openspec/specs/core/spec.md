# Spec: EasyPilot Core

## ADDED Requirements

### Requirement: System SHALL Provide 3D Drone Visualization
The system SHALL display a real-time 3D model of the drone that reflects its physical attitude.
#### Scenario: Load 3D model
- **Given** the iOS app is launched
- **When** the dashboard view appears
- **Then** the USDZ drone model shall be loaded and displayed in the SceneView

### Requirement: System SHALL Support Hybrid WiFi Connectivity
The system SHALL establish a connection between the iPhone and the ESP32 via WiFi, preferring a direct local path and falling back to a remote relay when the devices are not on the same subnet.
#### Scenario: Connect to drone on the local network
- **Given** the iPhone and ESP32 are powered on and share a WiFi subnet
- **When** the iOS app starts and reads the `esp32_ip` field in the incoming telemetry JSON
- **Then** the connection status shall be CONNECTED with a `LOCAL` badge and telemetry shall arrive directly via UDP on port 4242

#### Scenario: Connect to drone over the remote relay
- **Given** the iPhone is not on the same subnet as the ESP32
- **When** the iOS app starts
- **Then** the connection status shall be CONNECTED with a `RELAY` badge and telemetry shall arrive via the Mac/Mac-Mini Python relay over Ngrok-tunneled WebSocket

### Requirement: System SHALL Provide iPhone Motion Sensing
The iOS app SHALL read the iPhone's gyro and accelerometer data via CoreMotion and use it for tilt-based safety interactions only (no flight control). Detailed scenarios live in the change record `openspec/changes/sprint-03/specs/iphone-interaction/spec.md`.

### Requirement: System SHALL Provide a Phone-Side Simulator
The iOS app SHALL include a `Simulator` tab with a Mode-2 dual virtual joystick, rate-mode attitude physics, expo curves, and motor PWM visualization, operating entirely on-device with no commands sent to the real drone. Detailed scenarios live in the change record `openspec/changes/sprint-04/specs/simulator-controller/spec.md`.
