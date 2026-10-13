## Purpose

The phase 2 goal: a drone simulation with a physics engine that runs in the browser, built on the web viewer and delivered from the LeoCloud, so anyone can fly the drone without hardware (FSD §1.2, §10.2, US-07, US-08). Nothing of the simulation itself exists in code yet; the open work is tracked in the change `2026-10-13-phase2-web-simulator`.

## Requirements

### Requirement: Rigid-body drone physics

The web simulator SHALL simulate the drone as a rigid body with four motor thrusts, gravity, drag and ground contact, stepped at a fixed time step independent of the frame rate (§10.2, §15).

`status: not-implemented`

#### Scenario: Free fall
- **WHEN** the drone is armed with zero throttle in the air
- **THEN** it accelerates downwards at about 9.81 m/s² until it hits the ground

#### Scenario: Frame rate drop
- **WHEN** the frame rate drops from 60 to 30 fps
- **THEN** the flight path stays the same because physics uses a fixed step

### Requirement: Keyboard and gamepad control

The web simulator SHALL be controllable with the keyboard and with a gamepad through the Gamepad API in Mode 2 layout (§10.2, US-08).

`status: not-implemented`

#### Scenario: Gamepad connected
- **WHEN** a gamepad is connected and its left stick is pushed up
- **THEN** the throttle increases

### Requirement: Flight modes Rate, Angle and Hover

The web simulator SHALL offer Rate (acro), Angle (self-levelling) and Hover (brake, then hold position, height and heading) (§10.2, US-07).

`status: not-implemented`

#### Scenario: Hover
- **WHEN** Hover is switched on while flying at 5 m/s
- **THEN** the drone brakes and holds its position and height within ±0.2 m

### Requirement: HUD

The web simulator SHALL show height, speed, attitude, throttle and flight mode on screen (§10.2).

`status: not-implemented`

#### Scenario: Flying
- **WHEN** the drone climbs
- **THEN** the height value on the HUD increases

### Requirement: Delivered from the LeoCloud

The web simulator SHALL be reachable at `https://it220234.cloud.htl-leonding.ac.at/` without installation and without a local network to the drone (§3.3, §12.2, US-08).

`status: partial`

#### Scenario: Open URL
- **WHEN** a browser opens the production URL
- **THEN** the simulator loads (partial: image and manifests exist, but nothing is deployed yet and the page is still the viewer)
