# Tasks: Sprint 4 - Phone-Side Simulator & Controller Foundation

## Status Tracking
- [x] Phase 1: Preparation (OpenSpec Documentation)
- [x] Phase 2: VirtualJoystick component
- [x] Phase 3: DroneSimulator engine
- [x] Phase 4: SimulatorView tab
- [x] Phase 5: Tab wiring + Xcode project registration

---

## Detailed Task List

### Phase 1: Preparation
- [x] Create Sprint 4 Proposal
- [x] Create Simulator/Controller Specification
- [x] Create tasks.md

### Phase 2: VirtualJoystick component
- [x] Implement `VirtualJoystick.swift`
  - Circular pad with inner thumb circle
  - DragGesture tracking clamped to radius
  - Self-centering X/Y axes (spring animation on release)
  - Non-centering Y axis option (for throttle)
  - Expo curve applied to output values

### Phase 3: DroneSimulator engine
- [x] Implement `DroneSimulator.swift`
  - 20 Hz `Timer` driving physics
  - Rate-mode: stick → angular rate → attitude integration
  - Gravity return when disarmed / low throttle
  - Motor mixing from throttle + attitude
  - Configurable maxRollRate, maxPitchRate, maxYawRate, expo

### Phase 4: SimulatorView tab
- [x] Implement `SimulatorView.swift`
  - Mode 2 dual joystick layout
  - Sim / Live pill toggle (Live disabled with "Sprint 5" hint)
  - Arm / Disarm button
  - Horizon indicator + roll/pitch/yaw values
  - Four motor bars
  - Expo slider

### Phase 6: 3D World Polish (post-initial)
- [x] 3D scene with gravity physics (throttle needed to hover)
- [x] Propeller nodes (Prop_1…4) spin via SCNAction, speed tied to motor PWM
- [x] FPV camera (110° FOV, 15° up-tilt) + chase camera with yaw-aware lerp
- [x] Landmarks: orange home pad (H marking), 4 cardinal towers (N/S/E/W, 20m), 10m/20m distance rings, 14 trees
- [x] Fix attitude readout mid-screen: moved into cohesive bottom panel
- [x] Mini HorizonIndicator floating top-left below arm badge
- [x] Bottom panel as single frosted-glass slab (telemetry row + sticks)
- [x] `SimulatorScene.swift` (`UIViewRepresentable`) owns world setup + render delegate

### Phase 5: Wiring
- [x] Rename "Control" → "Algorithms" in `ContentView.swift`
- [x] Add Simulator tab to `ContentView.swift`
- [x] Register `VirtualJoystick.swift`, `DroneSimulator.swift`, `SimulatorView.swift` in `project.pbxproj`
