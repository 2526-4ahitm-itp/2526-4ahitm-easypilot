# Spec: Communication Protocols

This spec describes how the iOS app and the ESP32 talk to each other, and
how the ESP32 talks to the Betaflight flight controller. There are three
hops:

```
iOS app  ⟷ WiFi ⟷  ESP32  ⟷ UART/MSP ⟷  Betaflight FC
```

## ADDED Requirements

### Requirement: System SHALL Discover the Drone via UDP Beacon
The iOS app SHALL find the ESP32 without the user typing an IP, as long
as both are on the same WiFi network.

#### Scenario: Listen for beacon
- **Given** the iOS app is running
- **When** it starts up
- **Then** it binds a UDP listener on port 4242
- **And** it parses any incoming `EASYPILOT:<IP>` message

#### Scenario: ESP32 advertises itself
- **Given** the ESP32 is on WiFi
- **Then** every 5 s it broadcasts `EASYPILOT:<IP>` to
  `255.255.255.255:4242`

#### Scenario: Manual IP fallback
- **Given** the broadcast does not reach the iOS device (e.g. AP isolation)
- **When** the user enters an IP manually in the dashboard
- **Then** the iOS app uses that IP and skips beacon discovery

---

### Requirement: System SHALL Use WebSocket for Control + Telemetry
The iOS app SHALL connect to `ws://<esp32_ip>:81` and use a single
connection for bidirectional traffic.

#### Scenario: Telemetry inbound
- **Given** a connected WebSocket
- **Then** the ESP32 pushes a JSON telemetry frame every 100 ms with the
  fields specified in the firmware spec

#### Scenario: Commands outbound
- **Given** the iOS app wants to send a command
- **Then** it sends a single WebSocket TEXT frame containing the JSON
  command body (e.g. `{"cmd":"ARM"}`)

#### Scenario: Disconnect during SOUND/RC mode
- **Given** the ESP32 is in `SOUND` or `RC` mode
- **When** the WebSocket disconnects
- **Then** motors stop and mode reverts to `IDLE`

---

### Requirement: System SHALL Define a Versioned Command Vocabulary
All control commands SHALL be JSON objects with a `cmd` string field,
or one of the small allow-list of plain-text shortcuts.

#### Scenario: Supported commands
- **Given** the firmware spec
- **Then** the following commands SHALL be honoured exactly as documented:

  | Command | Payload | Effect |
  |---|---|---|
  | `{"cmd":"ARM"}` | – | `isArmed = true` |
  | `{"cmd":"DISARM"}` | – | `isArmed = false`, mode → IDLE, motors stop |
  | `{"cmd":"STOP"}` | – | Mode → IDLE, motors stop |
  | `{"cmd":"START_BALANCE", ...}` | `baseThrottle, kPRoll, kPPitch` | Enter BALANCE |
  | `{"cmd":"START_MANUAL", ...}` | full telemetry fields | Enter MANUAL |
  | `{"cmd":"START_SOUND","maxPWM":N}` | N clamped to 1000–1500 | Enter SOUND |
  | `{"cmd":"TILT_SOUND","pwm":N}` | – | All motors → N, refresh 1 s timeout |
  | `{"cmd":"START_RC", ...}` | `kPRoll, kPPitch` | Enter RC, zero stick state |
  | `{"cmd":"RC", ...}` | `thr, pit, rol, yaw` | Stick update, refresh 500 ms timeout |
  | `SAFE_TEST` (plain text) | – | M1 = 1050 for 500 ms (requires armed) |
  | `SIMULATE` (plain text) | – | Force `simMode = true` |

#### Scenario: Unknown command
- **Given** a JSON payload without a recognised `cmd`
- **And** the payload contains telemetry-shaped fields
- **Then** those fields override the live telemetry (used by the
  simulator to push attitudes for visualisation)

---

### Requirement: System SHALL Use MSP for FC Communication
The ESP32 SHALL exchange data with the Betaflight FC using the
MultiWii Serial Protocol over UART.

#### Scenario: Frame format
- **Given** the ESP32 wants to send/receive a frame
- **Then** the frame uses MSP v1 framing: `$ M < / > <size> <cmd> <payload…>
  <checksum>` where checksum = XOR of size, cmd, and payload bytes

#### Scenario: Supported MSP commands
- **Given** the firmware on the ESP32
- **Then** it requests `MSP_ATTITUDE (108)` and `MSP_ANALOG (110)` from
  the FC, and sends `MSP_SET_MOTOR (214)` to drive motors

#### Scenario: Bad checksum
- **Given** a received MSP frame
- **When** the computed checksum does not match the received one
- **Then** the frame is discarded and the parser logs `[MSP] Checksum
  error` to the serial console

---

### Requirement: System SHALL Send Telemetry at 10 Hz Steady-State
The end-to-end telemetry path SHALL deliver at least 10 updates per second
to the iOS app in nominal conditions.

#### Scenario: Update rate at the app
- **Given** a stable WebSocket connection
- **Then** the iOS app receives at least 10 telemetry frames per second
- **And** end-to-end latency (FC orientation change → app rotation) is
  under 200 ms (per `drone-telemetry` spec)
