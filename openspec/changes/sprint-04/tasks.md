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

### Phase 5: Wiring
- [x] Rename "Control" → "Algorithms" in `ContentView.swift`
- [x] Add Simulator tab to `ContentView.swift`
- [x] Register `VirtualJoystick.swift`, `DroneSimulator.swift`, `SimulatorView.swift` in `project.pbxproj`
