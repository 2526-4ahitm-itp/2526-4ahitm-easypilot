## 1. VirtualJoystick `isActive` binding

- [x] 1.1 Add `@Binding var isActive: Bool` to `VirtualJoystick` with a default-throwaway-`@State` initialiser for callers that don't observe it
- [x] 1.2 Set `isActive = true` in `.onChanged` (only when transitioning from false) and `isActive = false` in `.onEnded`
- [x] 1.3 Update existing `VirtualJoystick(...)` call sites in `SimulatorView` and `ControlView` to compile cleanly with the new optional binding
- [ ] 1.4 Manual check on device: tap-without-moving sets active true; lift sets it false; thumb-at-centre keeps it true

## 2. Auto-stabilize on right-stick release

- [x] 2.1 Add `@Published var rightStickActive: Bool = false` to `DroneSimulator` (or wire via existing input plumbing — pick the path that touches the fewest files)
- [x] 2.2 In `SimulatorView`, bind the right joystick's `isActive` to a `@State` and forward into `DroneSimulator` (or directly to the simulator's binding)
- [x] 2.3 In `DroneSimulator.update()`, when `flightMode == .rate AND rightStickActive == false AND armed AND throttle > 0.05`, replace the rate-mode integration with a balance-style P-controller targeting `(0°, 0°)` using `kPRoll`, `kPPitch`, `kPScale`
- [x] 2.4 Confirm balance mode behaviour is unchanged (P-controller already targets 0 when stick is centred)
- [x] 2.5 Confirm disarmed and low-throttle paths still hit the existing gravity-return / motors-at-1000 code
- [ ] 2.6 Tune so that from a 30° starting attitude with no thumb on the right stick, level (±1°) is reached within 1.5 s in rate mode

## 3. Landscape layout for SimulatorView

- [x] 3.1 Wrap `SimulatorView.body` in a `GeometryReader` and derive `isLandscape = proxy.size.width > proxy.size.height`
- [x] 3.2 Extract the existing portrait body into a `portraitLayout` private view; keep it byte-equivalent so portrait pilots see no regression
- [x] 3.3 Build a new `landscapeLayout` view: top header strip (≤ 40 pt), then a single `HStack` with left joystick (16 pt inset), centre column (horizon + roll/pitch/yaw + motor bars), right joystick (16 pt inset)
- [x] 3.4 Branch in `body`: render `landscapeLayout` when `isLandscape`, otherwise `portraitLayout`
- [ ] 3.5 Verify `@StateObject` `DroneSimulator` (and any other persistent state) survive the layout switch by confirming armed/roll/pitch don't reset on rotation
- [x] 3.6 Update Info.plist or scene config if needed so the Simulator tab is allowed in landscape (check current orientation-allowed list)

## 4. Live-mode placeholder copy update

- [x] 4.1 In `SimulatorView`, change the Sim/Live mode pill's denial message from "Available in Sprint 5" to "Available in a future sprint"

## 5. On-device verification

- [ ] 5.1 Build and deploy to the physical device with `./deploy.sh`
- [ ] 5.2 In portrait, fly briefly and confirm rate-mode and balance-mode feel unchanged when a thumb is on the stick
- [ ] 5.3 In portrait, release the right stick from a banked attitude and confirm the drone returns to level within ~1.5 s
- [ ] 5.4 Rotate to landscape mid-flight; confirm the layout switches cleanly with no overflow, no joystick clipping, no reset of `_roll/_pitch/armed`
- [ ] 5.5 Fly in landscape with both thumbs; confirm joysticks are reachable and not clipped at the screen edges
- [ ] 5.6 Rotate back to portrait; confirm portrait layout renders unchanged

## 6. Spec sync

- [x] 6.1 After implementation, run `openspec validate sprint-05` and resolve any spec/code drift
- [x] 6.2 Update `openspec/specs/simulator-controller/spec.md` only via the archive step — do not edit the canonical spec directly during implementation
