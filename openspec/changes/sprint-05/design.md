## Context

`SimulatorView` (570 lines) is laid out as a fixed top-down `VStack`: header on top, joysticks at the bottom, telemetry strip and horizon indicator in between. There is no `GeometryReader`, no `horizontalSizeClass` check, and no orientation-aware branching. On rotation to landscape, the same vertical stack is force-fit into a wide-but-short canvas — the joysticks end up cramped and overflow occurs.

`VirtualJoystick` already drives its own `DragGesture(minimumDistance: 0)` with `.onChanged` and `.onEnded`, so the touch lifecycle is observable internally. It currently does not surface that lifecycle to its parent — only the post-`onEnded` reset stick values (which are zero).

`DroneSimulator.update()` already implements two paths: a rate-mode integrator (with passive 20°/s gravity return when throttle is low or sim is disarmed) and a balance-mode P-controller (driving toward `target = stick × maxBalanceAngle`). Neither path knows whether the user has physically released the stick versus is holding it at zero — they both see "stick = (0, 0)" and behave identically.

## Goals / Non-Goals

**Goals:**
- The Simulator tab presents a usable, non-overlapping layout in both portrait and landscape orientations on the deployment target (iPhone 13 mini class).
- `VirtualJoystick` publishes a thumb-down signal that the simulator can consume.
- `DroneSimulator` actively levels roll and pitch when the right (attitude) stick has no thumb on it, regardless of flight mode, with sub-second convergence.
- Existing portrait behaviour is preserved exactly — no regression for portrait pilots.

**Non-Goals:**
- Device-tilt as a control input (no gyro-driven flight). The phone's orientation is used only to choose a layout, not to influence the drone.
- Landscape support for the Dashboard or Algorithms tabs — only Simulator is in scope.
- Persisting the orientation preference (the system handles it via `UIDevice` orientation).
- Live mode — explicitly deferred again.

## Decisions

### 1. Orientation detection — `horizontalSizeClass` + `GeometryReader`

**Decision:** Use SwiftUI's `@Environment(\.horizontalSizeClass)` together with a `GeometryReader` aspect-ratio check (`width > height`) inside `SimulatorView.body`. When the canvas is landscape-shaped, render the landscape branch; otherwise portrait.

**Alternatives considered:**
- `UIDevice.current.orientation` — reflects physical orientation, not interface orientation; flickers and does not match what SwiftUI is laying out.
- `verticalSizeClass == .compact` — works on iPhone but misclassifies iPad landscape (which we don't ship to, but it is still a worse signal).
- Hard-coding `UIInterfaceOrientationIsLandscape` checks — ties to UIKit lifecycle and conflicts with SwiftUI's declarative model.

**Rationale:** Aspect ratio from `GeometryReader` is what SwiftUI actually has to work with. Size-class is a useful secondary signal but not enough alone on iPhone.

### 2. Landscape layout shape

**Decision:** Landscape branch is a single `HStack`:
```
┌──────────────────────────────────────────────────────────────┐
│  [thin header strip: armed · mode · input toggle · battery]  │
├──────────┬─────────────────────────────────┬─────────────────┤
│          │                                 │                 │
│  LEFT    │   horizon · roll/pitch/yaw      │   RIGHT         │
│  STICK   │   four motor bars               │   STICK         │
│ THR/YAW  │                                 │  PCH/ROL        │
│          │                                 │                 │
└──────────┴─────────────────────────────────┴─────────────────┘
```
Joystick pads are sized as before; centre column gets the remaining width. Header is collapsed to a single 32–36 pt strip across the top.

**Alternatives considered:**
- Side-by-side joysticks both on the right (one-handed style) — breaks muscle memory for pilots used to thumb-on-each-side controllers.
- Header on the left edge — wastes width that is precious in landscape.

### 3. `isActive` binding on `VirtualJoystick`

**Decision:** Add `@Binding var isActive: Bool` to `VirtualJoystick`. The binding defaults to a throwaway `@State` via an extension initialiser so existing call sites don't need to change unless they care. Set the binding to `true` in `.onChanged` (debounced to once per gesture by checking the current value) and `false` in `.onEnded`.

**Alternatives considered:**
- Closure callback `onTouchStateChanged: (Bool) -> Void` — verbose at every call site, doesn't compose with `@ObservedObject` / `@Published` patterns the simulator uses.
- Inferring from `(centerX, centerY) != (0, 0)` — fails for thumb-at-centre; the whole point is to distinguish that case.

### 4. Auto-stabilize behaviour

**Decision:** In `DroneSimulator.update()`, when `rightStickActive == false` AND the simulator is armed AND throttle > 0.05, override the rate-mode "20°/s gravity return" with the balance-mode P-controller targeting `(0°, 0°)`. Use the same `kPRoll`, `kPPitch`, `kPScale` constants that balance mode already uses. Balance mode itself already produces this behaviour (target = `0 × maxBalanceAngle = 0`), so the override only changes rate-mode behaviour in practice.

**Alternatives considered:**
- Always force balance behaviour — removes the rate-mode feel even while the pilot has a thumb mid-flick.
- Tune the rate-mode gravity-return constant from 20°/s to 60°/s — works but is just a number; explicit "level-target" is more semantically clear and gives uniform behaviour across modes.

### 5. Gesture state stability across rotation

**Decision:** Don't try to preserve gesture state across rotation. Instead, ensure that on every layout rebuild the `isActive` binding is reset to `false` by the `VirtualJoystick`'s own `@State` lifecycle (a fresh view instance starts with no active touch). If a rotation interrupts a gesture, the simulator briefly sees `isActive == false` → auto-stabilize kicks in for one or two physics ticks → the user re-touches and overrides it. This is acceptable.

**Alternatives considered:**
- Lock orientation during gesture — fragile and surprising.
- Add a 100 ms debounce on `isActive` transitions — masks the cause; if rotation flicker is a real problem we add the debounce then.

## Risks / Trade-offs

- **[Risk]** Landscape layout puts joysticks at the screen edges, where iPhone reachability for some users is poor → **Mitigation**: inset the pads by 24 pt from each edge; revisit if pilots complain.
- **[Risk]** SwiftUI rebuilds the entire view tree on rotation; `DroneSimulator` is `@StateObject` in the parent so it survives, but `VirtualJoystick`'s `@State rawX/rawY` may not. Stick values are already `@Binding` in the parent, so the source of truth is safe. → **Mitigation**: verify on device after the layout change.
- **[Risk]** Auto-stabilize "fires when I rotate the phone" — see decision 5. → **Mitigation**: ship as-is; add debounce only if observed.
- **[Trade-off]** Header collapses in landscape, losing the verbose "ARMED" pill text in favour of a small dot indicator. We trade label clarity for joystick room.

## Open Questions

- Should landscape mode show the 3D drone scene (from Dashboard) in the centre column, or keep the existing horizon + motor bars? Current preference: existing horizon strip; the 3D scene is a Dashboard-tab concern.
- Should auto-stabilize also apply when the LEFT (throttle/yaw) stick is released — i.e., snap yaw rate to 0? Probably yes for symmetry, but the user's request only specified attitude. Leaving yaw alone for now; surface in tasks as a follow-up question.
