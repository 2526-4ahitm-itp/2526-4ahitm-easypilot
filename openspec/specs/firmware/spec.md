# Spec: ESP32 Firmware

The firmware is what runs on the ESP32-C3 SuperMini on the drone. There are
**two** firmware projects living under `PlatformIO/Projects/`:

| Project | Role |
|---|---|
| `EasyPilotIOS/` | Companion radio: talks to the iOS app over WiFi (WebSocket + UDP beacon) and forwards motor commands to the Betaflight FC over UART/MSP. This is the firmware the iOS app expects to find. |
| `easypilot/` | Standalone web-dashboard firmware: hosts a self-contained HTML control panel on port 80 with its own PID loop and takeoff/hover state machine. Used for desk testing and live demos without the phone. |

Both flash to the same board. Only one project is flashed at a time.

## ADDED Requirements

### Requirement: System SHALL Identify Itself Over the Network
The ESP32 firmware SHALL announce its IP address on the local network so
clients can discover it without manual configuration.

#### Scenario: UDP beacon advertises IP
- **Given** the ESP32 (`EasyPilotIOS/`) is connected to WiFi
- **When** 5 seconds have elapsed since the last beacon
- **Then** it broadcasts `EASYPILOT:<IP>` to `255.255.255.255:4242`

#### Scenario: Beacon stops on disconnect
- **Given** the ESP32 loses WiFi
- **Then** beacons stop until WiFi reconnects (auto-retry every 10 s)

---

### Requirement: System SHALL Provide WebSocket Command Surface
The ESP32 SHALL accept commands on `ws://<ip>:81` and stream telemetry to
all connected clients at 10 Hz.

#### Scenario: Telemetry broadcast format
- **Given** a client is connected
- **Then** the ESP32 broadcasts JSON every 100 ms containing fields
  `roll, pitch, yaw, m1, m2, m3, m4, voltage, batteryPercentage, armed,
  mode, fc`

#### Scenario: Accepts arming command
- **Given** a connected client
- **When** it sends `{"cmd":"ARM"}`
- **Then** `armed` becomes `true` and subsequent telemetry reflects it

---

### Requirement: System SHALL Implement Flight Modes
The firmware SHALL expose the following flight modes; all motor output
shall be clamped to PWM `[1000, 2000]`:

| Mode | Purpose | Trigger |
|---|---|---|
| `IDLE` | Motors at 1000, no control | Default; `DISARM`, `STOP` |
| `BALANCE` | P-controller on roll/pitch around `baseThrottle` | `START_BALANCE` |
| `MANUAL` | Motor and attitude values pushed by client | `START_MANUAL` |
| `SOUND` | All 4 motors run at the latest `TILT_SOUND` PWM | `START_SOUND` |
| `RC` | Angle-mode RC: throttle + roll/pitch/yaw targets | `START_RC` |

#### Scenario: Balance mixing
- **Given** mode is `BALANCE` and ARMED
- **When** roll error `eR` and pitch error `eP` are measured
- **Then** motors are set to
  - `M1 = baseThrottle − kPRoll·eR + kPPitch·eP` (rear-right CCW)
  - `M2 = baseThrottle − kPRoll·eR − kPPitch·eP` (front-right CW)
  - `M3 = baseThrottle + kPRoll·eR + kPPitch·eP` (rear-left CW)
  - `M4 = baseThrottle + kPRoll·eR − kPPitch·eP` (front-left CCW)

#### Scenario: Sound mode RX timeout
- **Given** mode is `SOUND` and ARMED
- **When** no `TILT_SOUND` packet arrives for 1 s
- **Then** all motors are forced to 1000

#### Scenario: RC mode RX timeout
- **Given** mode is `RC` and ARMED
- **When** no `RC` packet arrives for 500 ms
- **Then** motors stop and mode reverts to `IDLE`

---

### Requirement: System SHALL Talk MSP to the Flight Controller
For the `EasyPilotIOS/` firmware, the ESP32 SHALL speak the MultiWii
Serial Protocol over UART to a Betaflight-compatible FC.

#### Scenario: Wiring contract
- **Given** ESP32-C3 SuperMini
- **Then** GPIO 20 = UART1 RX (connect to FC TX pad)
- **And** GPIO 21 = UART1 TX (connect to FC RX pad)
- **And** baud rate = 115200, 8N1
- **And** GND shared between ESP32 and FC

#### Scenario: Telemetry polling
- **Given** firmware is running
- **Then** `MSP_ATTITUDE` (108) is requested every 100 ms
- **And** `MSP_ANALOG` (110) is requested every 500 ms
- **And** `MSP_SET_MOTOR` (214) is sent whenever the motor mixer updates
  (8 × uint16 PWM, last 4 always 1000)

#### Scenario: FC offline fallback
- **Given** no valid MSP response for 2 s and the drone is **not armed**
- **Then** `fcConnected = false` and `simMode = true` (firmware generates
  fake telemetry so the dashboard remains usable for demos)

---

### Requirement: System SHALL Implement Safety Watchdogs
The firmware SHALL fail safe whenever the link or attitude looks wrong.

#### Scenario: Heartbeat watchdog (web dashboard firmware)
- **Given** the `easypilot/` web dashboard firmware is running with motors armed
- **When** no `/heartbeat` HTTP request arrives for 1500 ms
- **Then** `drone_state = -1` (FAILSAFE), motors stop

#### Scenario: Crash detection (web dashboard firmware)
- **Given** the `easypilot/` web dashboard firmware is running with motors armed
- **When** `|roll| > 60°` or `|pitch| > 60°`
- **Then** `drone_state = -2` (CRASH), motors stop

#### Scenario: Pre-takeoff level check
- **Given** the user triggers `/start_time` or `/start_acc`
- **When** `|roll| > 5°` or `|pitch| > 5°`
- **Then** the firmware returns HTTP 400 and refuses to start

#### Scenario: Hard cap on throttle
- **Given** any flight mode
- **Then** motor PWM is hard-clamped to `[1000, MAX_THROTTLE]`
  (`MAX_THROTTLE = 1400` for the web-dashboard firmware)

---

### Requirement: System SHALL Support Over-the-Air Updates
The `easypilot/` firmware SHALL accept OTA flashes so the device does not
have to be re-cabled for every change.

#### Scenario: OTA reset on update start
- **Given** the firmware is running
- **When** an OTA upload begins
- **Then** flight state is reset (motors stopped, PID integrals cleared)
  before flashing
- **And** hostname is `ESP32-Drohne` and the OTA password is required
