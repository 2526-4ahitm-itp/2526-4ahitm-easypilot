## Why

Since 2026-09-14 the task is „Drohnensimulation mit Physik-Engine“ (FSD §1.2, §1.3): the real drone cannot fly because the DJI O4 Air Unit is broken. The Liftoff hover prototype (§11) proves the control algorithms, but it needs Windows, Liftoff and vJoy. The phase 2 deliverable is a simulator anyone can open in the browser from the LeoCloud (§10.2, US-08). Today `webinterface/frontend` only shows the model; there is no physics, no input and no deployment.

## What Changes

- Add a fixed-step rigid-body physics loop for the drone to the web frontend (§10.2, §15).
- Add keyboard and gamepad input in Mode 2 (§10.2, US-08).
- Port the flight modes from the iOS simulator and the Liftoff prototype: Rate, Angle and Hover (§10.2, §11, US-07).
- Add a HUD with height, speed, attitude, throttle and mode (§10.2).
- Remove the hard-coded `ws://localhost:8765` dependency from the simulator route so it works from the cloud (§10.1).
- Deploy backend and web simulator to the LeoCloud (§12.2, US-08, US-09).
- Add unit tests for the physics and controllers and run them in the Frontend workflow (§13).

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `web-simulator`: physics, input, flight modes, HUD and cloud delivery move from not-implemented to implemented (§10.2).
- `cloud-deployment`: the production deployment becomes live (§12.2).
- `ci-testing`: web simulator tests are added (§13).

## Impact

- **Frontend (React/three.js):** new simulator route with physics loop, input, controllers and HUD; possibly one new dependency for physics (decision in `design.md`).
- **Deployment:** `kubectl apply` of the existing manifests in namespace `student-it220234`.
- **CI:** Frontend workflow additionally runs the unit tests.
- **Liftoff prototype:** stays as reference; its controller gains are the starting point.
