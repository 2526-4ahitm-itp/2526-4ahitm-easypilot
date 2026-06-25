# Tasks: Sprint 5 - Landscape UI & Touch-Aware Stabilization

## Status Tracking
- [x] Phase 1: OpenSpec documentation
- [x] Phase 2: VirtualJoystick `isTouching` binding
- [x] Phase 3: DroneSimulator auto-level-on-release
- [x] Phase 4: SimulatorView landscape redesign
- [x] Phase 5: Wire touch state through SimulatorView
- [x] Phase 6: Build + on-device verification

---

## Detailed Task List

### Phase 1: OpenSpec documentation
- [x] proposal.md
- [x] tasks.md
- [x] specs/simulator-controller/spec.md (delta on existing spec)

### Phase 2: VirtualJoystick `isTouching` binding
- [x] Add `isTouching: Binding<Bool>` parameter (default `.constant(false)` for backwards compat)
- [x] Set true on `.onChanged`, false on `.onEnded`

### Phase 3: DroneSimulator auto-level-on-release
- [x] Add `sticksTouched: Bool` field (read on render thread, written from main)
- [x] RATE mode: skip gravity return while sticks touched; on release apply the existing 30°/s nudge toward 0 for roll and pitch (yaw rate already decays via angularDrag)
- [x] BALANCE mode: when sticks released, target roll/pitch becomes 0 (P-controller levels). When touched, target = stick × maxBalanceAngle (existing behaviour).

### Phase 4: SimulatorView landscape redesign
- [x] Strip full-width bottom slab from `landscapeOverlay`
- [x] Corner-anchored joystick pads with floating frosted-glass background
- [x] Top-left telemetry pill (compact horizontal layout: ROL · PCH · YAW · ALT · SPD)
- [x] Top-bar (mode toggle, SIM/LIVE, camera) untouched
- [x] Side drawer (right edge) for RATE expo / BALANCE kP settings
- [x] Floating centered arm button at bottom edge

### Phase 5: Wire touch state through SimulatorView
- [x] Add `@State leftTouching`, `@State rightTouching`
- [x] Pass bindings into both `VirtualJoystick` instances (portrait + landscape call sites)
- [x] On change, push `sim.sticksTouched = leftTouching || rightTouching`

### Phase 6: Build + verify
- [x] `./deploy.sh` builds clean
- [x] Portrait simulator unchanged
- [x] Landscape: 3D scene visible behind floating UI, settings drawer slides from right
- [x] Stick-release auto-level works in RATE and BALANCE
