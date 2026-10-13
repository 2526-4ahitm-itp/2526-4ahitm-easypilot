## Context

- `webinterface/frontend` is React 19 + Vite + @react-three/fiber; `Model.jsx` loads `drohne-compressed.glb` and rotates it from a WebSocket on `ws://localhost:8765`.
- Two working controllers already exist:
  - `EasyPilotIOS/EasyPilotIOS/DroneSimulator.swift`: rate/balance/POSHOLD physics, altitude PID with tilt compensation.
  - `simulator/liftoff-hover/hover.py`: cascaded position → tilt → rate controller and a climb-rate integral, verified in Liftoff and by closed-loop tests.
- Images and manifests for the LeoCloud exist (`k8s/`, `images.yml`), nothing is deployed.

## Goals / Non-Goals

**Goals:**
- Fly the drone in the browser with gravity, thrust and drag, at a frame-rate independent time step.
- Rate, Angle and Hover modes with the same feel as the iOS simulator and the Liftoff prototype.
- Live at `https://it220234.cloud.htl-leonding.ac.at/`.

**Non-Goals:**
- Connection to the real drone (no Air Unit).
- Multiplayer, recording/replay, obstacle courses (FSD §18 „Kann“).

## Decisions

- **Own integrator instead of a full physics engine (proposal, to be confirmed by the team).** A quadcopter needs one rigid body, four thrust forces, drag and a ground plane. A semi-implicit Euler step at 500 Hz (like Liftoff) in plain TypeScript/JS is small, testable without a browser and has no new dependency. A library such as `@react-three/rapier` or `cannon-es` is the alternative if collisions with scenery are needed later; the physics module is written behind an interface so it can be swapped.
- **Fixed step, render interpolation.** Physics runs in an accumulator loop (`while (acc >= DT) step(DT)`), rendering uses the latest state. This keeps flight paths identical at 30 and 60 fps (FSD §15).
- **Controllers ported, not reinvented.** Rate/Angle from the iOS `DroneSimulator`, Hover from `hover.py` (`HoverController.step`), with the same gains as starting point. The closed-loop tests of `test_hover.py` are ported to Vitest.
- **Input through the Gamepad API plus keyboard fallback.** Mode 2: left stick throttle/yaw, right stick pitch/roll; keys W/S throttle, A/D yaw, arrows pitch/roll, H hover.
- **Telemetry viewer stays separate.** The existing `/model` page keeps its WebSocket; the simulator gets its own route and does not depend on `localhost`.
- **Vitest as test runner** (new dev dependency, needs team approval per the project rules); it integrates with Vite and runs headless in the existing Frontend workflow.

## Risks / Trade-offs

- [Own integrator feels wrong] → tune with the gains from Liftoff, compare climb/brake times with the Liftoff measurements (stop from 16 m/s in about 2 s).
- [Gamepad API differences between browsers] → keyboard fallback, test in Chrome and Firefox.
- [LeoCloud quotas] → web image is static nginx, backend small; both fit the namespace limits.

## Open Questions

- Own integrator or library? (FSD §19)
- Does the backend store anything for the simulator (best times, recordings)?
- Remaining dates and milestones of phase 2.
