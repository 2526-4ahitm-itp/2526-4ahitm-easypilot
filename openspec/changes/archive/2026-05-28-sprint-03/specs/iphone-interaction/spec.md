# Spec: iPhone Interaction & Deployment

## ADDED Requirements

### Requirement: System SHALL Monitor iPhone Motion
The iOS app SHALL read the iPhone's gyro and accelerometer data using CoreMotion and display its orientation (Pitch/Roll) in the dashboard.
#### Scenario: Visualize iPhone tilt
- **Given** the iOS app is running on a physical device
- **When** the user tilts the iPhone
- **Then** a small icon or indicator shall show the iPhone's tilt in real-time

### Requirement: System SHALL Implement Safe Test Trigger
Tilting the iPhone past a 45-degree angle SHALL NOT arm the motors but SHALL trigger a low-power motor pulse (1050 PWM) or a UI visual feedback as a safety measure.
#### Scenario: Trigger safe motor test
- **Given** the drone is connected and stationary
- **When** the iPhone is tilted past 45 degrees
- **Then** the app shall send a command to spin Motor 1 at minimum throttle for 500ms

### Requirement: System SHALL Use Hybrid Connectivity
The iOS app SHALL automatically attempt a direct local WebSocket connection before falling back to the Ngrok relay.
#### Scenario: Connect locally
- **Given** the iPhone and ESP32 are on the same WiFi network
- **When** the app starts
- **Then** the app shall prioritize the local IP of the ESP32

### Requirement: System SHALL Support Fast USB Deployment
A script on the Mac Mini SHALL allow building and installing the Xcode project to a connected iPhone via USB without manual UI steps.
#### Scenario: One-click deploy
- **Given** the iPhone is connected to the Mac Mini via USB
- **When** the user runs ./deploy.sh
- **Then** the project shall be compiled and launched on the iPhone
