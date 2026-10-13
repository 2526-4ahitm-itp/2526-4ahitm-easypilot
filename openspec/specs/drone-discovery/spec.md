## Purpose

How the iOS app finds the drone without the user typing an IP: the ESP32 broadcasts a UDP beacon, the app listens for it and connects; a manual IP entry covers networks where broadcasts do not arrive (FSD §5.1, US-03).

## Requirements

### Requirement: UDP beacon from the ESP32

The ESP32 SHALL broadcast `EASYPILOT:<IP>` to `255.255.255.255:4242` every 5 seconds while it is connected to WiFi (§5.1).

`status: implemented`

#### Scenario: Beacon interval
- **WHEN** the ESP32 is on WiFi and 5 s have passed since the last beacon
- **THEN** it broadcasts `EASYPILOT:<own IP>` on UDP port 4242

#### Scenario: WiFi lost
- **WHEN** the ESP32 loses WiFi
- **THEN** no beacons are sent until it has reconnected

### Requirement: Automatic connection from the app

The iOS app SHALL listen on UDP port 4242, parse `EASYPILOT:<IP>` and open the WebSocket to that IP without user interaction (§5.1, US-03).

`status: implemented`

#### Scenario: Zero-config connect
- **WHEN** the app starts on the same WiFi as the ESP32
- **THEN** it connects to `ws://<IP>:81` after receiving the first beacon

### Requirement: Manual IP fallback

The Dashboard SHALL let the user enter an IP and connect to it when no beacon arrives (§5.1, §8.1). The entered IP SHALL be remembered across app launches.

`status: partial`

#### Scenario: Manual connect
- **WHEN** the user enters an IP and taps connect
- **THEN** the app opens the WebSocket to that IP

#### Scenario: IP remembered
- **WHEN** the app is restarted after a manual connect
- **THEN** the last manual IP is pre-filled (not implemented: the field is a plain `@State`)
