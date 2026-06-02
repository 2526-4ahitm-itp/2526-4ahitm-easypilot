## Why

Two simulator-tab pain points stand in the way of a smooth piloting experience:

1. **The simulator UI breaks when the device rotates into landscape.** The current `SimulatorView` is laid out as a single fixed `VStack` (header on top, joysticks at the bottom) and assumes portrait dimensions. When the user holds the phone horizontally — which is the natural grip for thumb-stick piloting — controls overflow, the telemetry strip squishes, and joystick pads end up too close together or off-screen.
2. **The drone does not actively level out when the right (attitude) stick is released.** In rate mode it drifts back slowly via gravity-return; in balance mode it relies on the target snapping to 0 — but neither distinguishes "thumb at centre" from "no thumb at all". A held-but-centred thumb behaves the same as a released stick, and there is no signal that says "the pilot has let go, take over and stabilize".

Sprint-05 fixes both: a proper landscape layout for the simulator and a thumb-aware auto-stabilize behaviour that mirrors how a real self-levelling drone feels.

## What Changes

- **Landscape support for the Simulator tab.** `SimulatorView` switches to a horizontal arrangement when the device is in landscape: left joystick pad on the left side of the screen, right joystick pad on the right, telemetry / horizon indicator centred between them, header collapsed into a thin top bar. Portrait layout is preserved unchanged.
- **`VirtualJoystick` reports thumb-down state.** Add an `isActive` binding that is `true` while a finger is on the pad and `false` when no finger is down — independent of the stick's `(x, y)` deflection.
- **Auto-stabilize on stick release in `DroneSimulator`.** When the simulator is armed, throttle > 0.05, and the right (attitude) stick reports `isActive == false`, the simulator drives roll and pitch toward 0° using the existing balance-mode P-controller — regardless of whether the flight mode is rate or balance. When `isActive == true` (including thumb-at-centre), the user's current flight mode handles the input as before.
- **Defer Live mode.** The sprint-04 placeholder "Available in Sprint 5" on the sim/live toggle is updated to "Available in a future sprint".

## Capabilities

### New Capabilities
<!-- none — extending an existing capability -->

### Modified Capabilities
- `simulator-controller`: adds a landscape-orientation layout requirement, a joystick `isActive` reporting requirement, and a thumb-release auto-stabilize requirement. Revises the Sim/Live placeholder copy.

## Impact

- **Code touched**: `EasyPilotIOS/EasyPilotIOS/SimulatorView.swift`, `DroneSimulator.swift`, `VirtualJoystick.swift`. Likely small touch on `DesignSystem.swift` if shared layout helpers are needed.
- **No firmware changes**: iOS-app-only; ESP32 is not involved.
- **No new dependencies**: SwiftUI's existing orientation primitives (`GeometryReader` / `horizontalSizeClass` / `verticalSizeClass`) are sufficient.
- **UX**: portrait pilots see no difference except the auto-stabilize behaviour (which they may notice as "the drone settles faster when I let go"). Landscape pilots get a working layout for the first time.
- **Risk**: SwiftUI layout rebuilds during rotation can momentarily reset gesture state — auto-stabilize must not double-trigger because `isActive` flickers during a layout transition.
