# Specifications: Sprint 2 - Real-time MSP Telemetry & Battery Monitoring

## Overview
This specification covers the implementation of real-time data flow from the Flight Controller (FC) to the iOS app using the MSP protocol over a WebSocket-to-UDP relay.

## Data Structure (MSP)
* **MSP_ATTITUDE (108):** Extract Roll, Pitch, Yaw.
* **MSP_ANALOG (110):** Extract Battery Voltage (V) and Cell Count.

## ESP32 Implementation (PlatformIO)
* **UART Communication:** Use `HardwareSerial` to request MSP packets from FC.
* **WebSocket Client:** Use `arduinoWebSockets` to send JSON data to the Relay Server.
* **Frequency:** Minimum 10Hz for attitude, 2Hz for battery.

## iOS App (SwiftUI)
* **Telemetry Model:** Update `DroneTelemetry` struct to include `voltage` and `m1-m4`.
* **UDP Listener:** Continuous background listening on port 4242 with keep-alive PING.
* **Visualization:** Update `SceneKit` drone orientation based on attitude data.
* **UI Components:** Glassmorphism cards for telemetry, vertical bars for motor output.

## Relay Server (Python)
* **WebSocket Endpoint:** Listen on port 8080 for ESP32 connection.
* **UDP Broadcast:** Send received data to `255.255.255.255` and `127.0.0.1` on port 4242.
