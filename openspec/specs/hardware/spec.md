# Spec: Hardware Platform

This spec captures the physical platform the firmware is written against.
Hardware changes (different board, different FC, different ESCs) ripple
into both the firmware spec and the communication spec, so every change
should start from updates here.

## ADDED Requirements

### Requirement: System SHALL Run on an ESP32-C3 SuperMini
The companion firmware SHALL target the ESP32-C3 SuperMini.

#### Scenario: PlatformIO environment
- **Given** the firmware project
- **Then** `platformio.ini` sets `board = esp32-c3-devkitm-1` and
  `framework = arduino`

#### Scenario: USB CDC for serial
- **Given** the ESP32-C3 SuperMini has only the USB-C port
- **Then** build flags `-D ARDUINO_USB_MODE=1` and
  `-D ARDUINO_USB_CDC_ON_BOOT=1` SHALL be set so the USB-C port acts as
  the serial monitor

---

### Requirement: System SHALL Connect to a Betaflight Flight Controller
The companion firmware SHALL drive the motors through a Betaflight-flashed
flight controller, not directly through the ESP32.

#### Scenario: UART wiring
- **Given** the ESP32-C3 SuperMini
- **Then** GPIO 20 = UART1 RX, wired to the FC's TX pad
- **And** GPIO 21 = UART1 TX, wired to the FC's RX pad
- **And** GND is shared between ESP32 and FC

#### Scenario: Baud rate
- **Given** the FC is configured for MSP on the chosen UART
- **Then** both sides use 115200 baud, 8N1

---

### Requirement: System SHALL Operate ESCs With Standard PWM Ranges
All motor commands SHALL respect the standard 1000–2000 µs PWM range
used by Betaflight and the connected ESCs.

#### Scenario: PWM clamping
- **Given** any motor command from any flight mode
- **Then** the output PWM is clamped to `[1000, 2000]`
- **And** `1000` means "motor stopped"
- **And** the web-dashboard firmware uses a stricter ceiling
  `MAX_THROTTLE = 1400` for safety during tethered tests

#### Scenario: Quadrotor-X geometry
- **Given** the standard quadrotor-X frame
- **Then** motors are numbered M1 (rear-right, CCW), M2 (front-right, CW),
  M3 (rear-left, CW), M4 (front-left, CCW)
- **And** roll/pitch mixing follows the table documented in
  `firmware/spec.md`

---

### Requirement: System SHALL Monitor LiPo Battery
The platform SHALL report battery voltage and a derived percentage to
the iOS app so the pilot can land before brownout.

#### Scenario: Voltage source
- **Given** the FC is wired to the LiPo through the standard VBAT pad
- **Then** the FC reports voltage via `MSP_ANALOG` (110)
- **And** the ESP32 polls `MSP_ANALOG` at 2 Hz and forwards `voltage`
  and `batteryPercentage` in the next telemetry frame

#### Scenario: Critical voltage warning
- **Given** the battery is a 4S LiPo (nominal 16.8 V full, 14.0 V critical)
- **When** voltage drops below 14.0 V
- **Then** the iOS battery indicator turns red (per `drone-telemetry/spec.md`)
