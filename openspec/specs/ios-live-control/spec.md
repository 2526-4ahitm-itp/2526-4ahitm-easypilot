## Purpose

LIVE mode of the Simulator tab: the same joysticks fly the real drone through the firmware's RC mode (FSD §8.4, US-05). Implemented on 2026-05-28; it could not be flight-tested any more after the Air Unit defect.

## Requirements

### Requirement: SIM / LIVE switch

The Simulator tab SHALL offer a SIM/LIVE switch; LIVE SHALL only be selectable while connected to the drone, and leaving LIVE while armed SHALL send `DISARM` (§8.4).

`status: implemented`

#### Scenario: Not connected
- **WHEN** the user selects LIVE without a WebSocket connection
- **THEN** the hint „Not connected to drone“ is shown and the mode stays SIM

### Requirement: RC packets from the joysticks

When armed in LIVE mode the app SHALL send `ARM` and `START_RC {kPRoll,kPPitch}`, then an `RC {thr,pit,rol,yaw}` packet every 100 ms while armed and connected; disarming SHALL send `DISARM` and stop the packets (§8.4, §5.2).

`status: implemented`

#### Scenario: Arm in LIVE
- **WHEN** the user arms in LIVE with throttle at zero
- **THEN** `ARM` and `START_RC` are sent, followed by `RC` packets every 100 ms

### Requirement: Flight-tested with the real drone

LIVE mode SHALL be verified in a real flight (§1.3, US-05).

`status: not-implemented`

#### Scenario: Test flight
- **WHEN** the drone is flown in LIVE mode
- **THEN** it follows the joysticks (not possible since the Air Unit defect)
