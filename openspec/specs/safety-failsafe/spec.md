## Purpose

Fail-safe behaviour across firmware and app: motors off by default, watchdogs that stop the motors when input stops, emergency stops on dangerous attitude, and keeping credentials out of the repository (FSD §7).

## Requirements

### Requirement: Disarmed by default

After boot the drone SHALL be disarmed with all motors at 1000, and every mode other than IDLE SHALL require `ARM` first (§7.1).

`status: implemented`

#### Scenario: Command before arming
- **WHEN** `START_SOUND` is sent right after boot
- **THEN** the motors stay at 1000

### Requirement: Stop on disconnect in SOUND and RC

When the WebSocket client disconnects while the firmware is in SOUND or RC, the firmware SHALL stop the motors and switch to IDLE (§7.1).

`status: implemented`

#### Scenario: Phone leaves WiFi
- **WHEN** the app disconnects during RC
- **THEN** m1–m4 become 1000 and the mode is IDLE

### Requirement: Input watchdogs

The firmware SHALL stop the motors when no `TILT_SOUND` arrives for 1 s in SOUND, and stop the motors and switch to IDLE when no `RC` arrives for 500 ms in RC (§7.2).

`status: implemented`

#### Scenario: RC timeout
- **WHEN** RC is active and 500 ms pass without an `RC` packet
- **THEN** the motors stop and the mode becomes IDLE

### Requirement: Emergency stop on phone tilt

In Sound Mode the app SHALL stop Sound Mode and stop sending `TILT_SOUND` when the phone's combined tilt exceeds 60°; the firmware watchdog then stops the motors (§7.2, US-02).

`status: implemented`

#### Scenario: Phone dropped
- **WHEN** the tilt reaches 60.1°
- **THEN** Sound Mode stops; at exactly 60° it keeps running

### Requirement: Standalone firmware watchdogs

The standalone web firmware SHALL enter FAILSAFE when no heartbeat arrives for 1.5 s, CRASH when roll or pitch exceed 60°, and refuse a start when roll or pitch exceed 5° (§7.2, §9).

`status: implemented`

#### Scenario: Browser tab closed
- **WHEN** the dashboard stops sending `/heartbeat` for 1.5 s while flying
- **THEN** `drone_state = -1` and the motors stop

### Requirement: Credentials never committed

WiFi and OTA credentials SHALL only live in gitignored files created from committed templates (§7.3).

`status: implemented`

#### Scenario: Fresh clone
- **WHEN** the repository is cloned
- **THEN** it contains `secrets.ini.example` / `wifi_secrets.example.h` but no real credentials (history cleaned on 2026-10-12; the exposed WiFi passwords still have to be changed)
