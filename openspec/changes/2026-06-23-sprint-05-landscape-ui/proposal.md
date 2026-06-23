# Proposal: Sprint 5 - Landscape UI & Touch-Aware Stabilization

## Goal
As a pilot using the Simulator tab, I want the controller UI to feel native in landscape orientation (the natural way to hold a phone for FPV-style flight) so the 3D scene remains visible behind floating, corner-anchored controls instead of being covered by a full-width slab. Additionally, the simulator should only auto-level the drone when my fingers leave the sticks — while I'm actively touching a stick, the drone should hold the commanded attitude/rate, matching the muscle-memory of real FPV gear.

## Context
Sprint 4 shipped a Simulator tab with portrait + landscape layouts, but the landscape variant just rearranges the portrait widgets — joysticks float at the bottom, but a frosted full-width bottom bar still covers ~25% of the 3D view. On a wide canvas this wastes screen real estate; corner-anchored controls are standard in mobile flight sims (DJI Fly, Tello, Liftoff Mobile).

Currently both RATE and BALANCE physics auto-level the drone the moment stick input returns to zero (gravity return at 30°/s in rate mode, P-controller pulling toward zero target in balance mode). Real FPV controllers are mechanical sticks that *stay deflected* until the pilot releases them — releasing a stick is a deliberate "give me back to neutral" gesture. The simulator should distinguish "stick released" (snap back / level out) from "stick held at center" (hold current attitude). Touch events on the joystick pads (`DragGesture.onChanged` / `.onEnded`) provide the signal.

## Acceptance Criteria

### Landscape UI
* Landscape (compact vertical size class) layout shows the 3D scene unobstructed across the **full width and full height** of the screen.
* Joystick pads are anchored in the bottom-left and bottom-right corners as **floating glass disks**, no continuous bar behind them.
* Telemetry (roll / pitch / yaw / alt / speed) is presented as a **compact pill** in the top-left or top-center, not as a bottom slab.
* Flight-mode selector (RATE / BALANCE) and SIM / LIVE toggle remain reachable in the top bar.
* Settings (expo / kP) open as a **side drawer from the right edge** that overlays only the right portion of the screen, not the whole bottom.
* Arm/disarm button floats centered at the bottom between the joysticks.
* Portrait layout (regular vertical size class) is unchanged.

### Touch-aware stabilization
* `VirtualJoystick` exposes an `isTouching: Binding<Bool>` set `true` during `DragGesture.onChanged` and `false` on `.onEnded`.
* `DroneSimulator` exposes a `sticksTouched: Bool` flag.
* In **RATE mode**: while `sticksTouched == true`, no gravity-return; attitude only responds to commanded rate. On release, roll and pitch drift toward 0 at a configured rate (gravity return).
* In **BALANCE mode**: while `sticksTouched == true`, the P-controller holds the target angle derived from current stick values without snapping back to 0; on release, target reverts to 0 and the P-controller levels the drone.
* Touching either stick (left or right) counts as "touching" — the flag is the OR of both.
* Throttle behavior is unchanged (still non-centering on release).
