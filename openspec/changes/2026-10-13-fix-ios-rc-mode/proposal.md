## Why

The firmware reports `"mode":"RC"` while the LIVE mode flies the drone (FSD §6, §8.4). The app's `FlightMode(rawOrIdle:)` has no RC case and maps it to IDLE, so the Algorithms tab hides its STOP button although the motors may be running (§7.1, §8.2). This was found during coaching round 1 (AP7, left open in `2026-10-12-coaching-r1`).

## What Changes

- Add an `rc` case to `FlightMode` so `"RC"` is shown as RC (§5.3).
- Show the STOP button in the Algorithms tab for every mode other than IDLE, including RC (§8.2).
- Add `startRC` and `rc` cases to `DroneCommand` and use them in `SimulatorView` instead of hand-built strings (§5.2).
- Flip the characterization test `rcModeIsCurrentlyReportedAsIdle` to expect `.rc` and add payload tests for the RC commands.

## Capabilities

### Modified Capabilities
- `telemetry-stream`: flight mode mapping covers RC (§5.3).
- `ios-algorithms`: STOP button visible during RC (§8.2).
- `command-protocol`: RC commands built through `DroneCommand` (§5.2).

## Impact

- iOS: `FlightMode.swift`, `DroneCommand.swift`, `ControlView.swift`, `SimulatorView.swift`, tests in `EasyPilotIOSTests`.
- No firmware change; the wire format stays the same.
