## Purpose

The Python helpers in `webinterface/backend/src/main/python`: a relay that forwards telemetry from a WebSocket to UDP broadcasts in the LAN (optionally exposed through Ngrok), and an MSP sender that reads the FC over USB serial for the web viewer (FSD §5.5). Both run on a laptop in the drone's WiFi, not in the cloud.

## Requirements

### Requirement: WebSocket to UDP relay

`relay_server.py` SHALL accept WebSocket connections on port 8080 and forward every received message unchanged as a UDP broadcast to port 4242 and to localhost (§5.5).

`status: implemented`

#### Scenario: Message relayed
- **WHEN** a client sends a JSON telemetry string to `ws://<host>:8080`
- **THEN** the same string is broadcast on UDP 4242

### Requirement: Remote access through a tunnel

`start_system.sh` SHALL start an Ngrok tunnel to port 8080, print the public URL for the ESP32 and then start the relay (§5.5).

`status: implemented`

#### Scenario: Start system
- **WHEN** `./start_system.sh` runs with Ngrok installed and authenticated
- **THEN** the public tunnel URL is printed and the relay is running

### Requirement: Relay path visible in the app

When telemetry arrives through the relay instead of directly from the ESP32, the app SHALL show a `RELAY` badge (§5.5).

`status: not-implemented`

#### Scenario: Remote telemetry
- **WHEN** the app receives telemetry through the relay
- **THEN** a `RELAY` badge is visible (not implemented in the app)

### Requirement: MSP sender for the web viewer

`websocket_sender.py` SHALL read attitude from the FC over USB serial with MSP and serve it on `ws://localhost:8765` as JSON messages of type `attitude` and `motor_data` (§5.5, §10.1).

`status: implemented`

#### Scenario: Viewer connected
- **WHEN** the web viewer connects to port 8765 while the FC is plugged in
- **THEN** it receives `attitude` messages with roll, pitch and yaw

### Requirement: Tests for the Python helpers

The relay and MSP sender SHALL have automated tests (§13).

`status: not-implemented`

#### Scenario: CI run
- **WHEN** CI runs
- **THEN** relay forwarding is tested (no tests exist; `test_ws.py` is a manual script)
