## Purpose

The physical platform EasyPilot was built on in phase 1: an iFlight Nazgul ECO quad with a Betaflight flight controller, an ESP32-C3 SuperMini companion wired over UART, standard ESC PWM ranges and a LiPo battery (FSD §3.1, §4). Firmware, MSP and telemetry specs depend on the contracts here. Since phase 2 (§1.3) the real drone cannot be flown because the DJI O4 Air Unit is broken.

## Requirements

### Requirement: ESP32-C3 SuperMini companion target

The companion firmware SHALL target the ESP32-C3 SuperMini with the Arduino framework, and the USB-C port SHALL act as serial console (USB CDC on boot) (§3.1, §4.1).

`status: implemented`

#### Scenario: PlatformIO environment
- **WHEN** `PlatformIO/Projects/EasyPilotIOS/platformio.ini` is read
- **THEN** it targets an ESP32-C3 board with `framework = arduino` and sets `ARDUINO_USB_MODE=1` and `ARDUINO_USB_CDC_ON_BOOT=1`

### Requirement: UART wiring to the flight controller

The ESP32 SHALL connect to the Betaflight flight controller on UART1 with GPIO 20 as RX, GPIO 21 as TX, 115200 baud 8N1 and a shared ground (§4.1).

`status: implemented`

#### Scenario: Pin and baud contract
- **WHEN** the firmware opens the FC serial port
- **THEN** it uses RX = GPIO 20, TX = GPIO 21 at 115200 baud

### Requirement: Standard ESC PWM range

Every motor command SHALL be clamped to the PWM range 1000–2000 µs, where 1000 means motor stopped (§4.2).

`status: implemented`

#### Scenario: Out-of-range value clamped
- **WHEN** any flight mode computes a motor value outside 1000–2000
- **THEN** the value sent to the FC is clamped into that range

### Requirement: Battery voltage from the FC

The platform SHALL report LiPo voltage measured by the FC via `MSP_ANALOG` and derive a battery percentage linearly between 13.0 V (0 %) and 16.8 V (100 %) for a 4S pack; 14.0 V is the critical warning level (§4.3).

`status: implemented`

#### Scenario: Voltage forwarded
- **WHEN** a valid `MSP_ANALOG` response arrives
- **THEN** `voltage` and `batteryPercentage` in the next telemetry frame reflect it

### Requirement: Working video and radio link

The drone SHALL provide a working FPV video and radio link through the DJI O4 Air Unit so it can be flown with goggles and remote (§1.1, §1.3).

`status: not-implemented`

#### Scenario: Air Unit defect
- **WHEN** the drone is powered
- **THEN** no video and no goggle/remote control is available, because the Air Unit is broken since before 2026-09-14; repair or replacement is an open point (§19)
