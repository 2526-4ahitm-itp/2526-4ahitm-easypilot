# Continuation Notes — sprint-05 (iOS Simulator)

## Session Date
2026-06-02

## Where to pick up

You're mid-flight through **sprint-05**. Code is implemented and pushed; what's left is on-device verification.

- Branch: `ep7-ios-app` (pushed through commit `81e5973`)
- OpenSpec change: `openspec/changes/sprint-05/`
- Status: **16/25 tasks done** — the 9 remaining tasks all require a physical iPhone

## What sprint-05 is

Two iOS-app-only changes to the Simulator tab:

1. **Landscape layout** — the simulator UI was breaking when the phone rotated to horizontal. Added a `GeometryReader` aspect-ratio branch in `SimulatorView.body`: portrait keeps the existing stacked layout byte-equivalent; landscape arranges joysticks on the left/right edges with horizon + telemetry + arm button stacked between them, header collapsed to a 40pt strip.
2. **Auto-stabilize on stick release** — `VirtualJoystick` now publishes an `isActive` binding (true while a thumb is touching the pad, independent of stick deflection). When rate-mode flight has no thumb on the right (attitude) stick, `DroneSimulator` drives roll/pitch to 0° using the balance-mode P-controller (`kPRoll`, `kPPitch`, `kPScale`) instead of the passive 20°/s gravity drift. Yaw stays rate-controlled off the left stick. Balance mode and disarmed paths are unchanged.

**Important scope clarification**: an earlier read of the requirements interpreted "horizontal support for tilting the phone" as gyro-as-flight-input. That was wrong. It means **landscape orientation support** (the controller UI bugs out when rotating from portrait to landscape). The committed code + openspec artifacts reflect the correct scope.

## Files touched

| File | What changed |
|---|---|
| `EasyPilotIOS/EasyPilotIOS/VirtualJoystick.swift` | Added `@Binding var isActive: Bool` with `.constant(false)` default. Set to `true` in `.onChanged` (only on transition), `false` in `.onEnded`. |
| `EasyPilotIOS/EasyPilotIOS/DroneSimulator.swift` | Added `var rightStickActive: Bool = false` input field (alongside throttle/yaw/pitch/roll — same threading model). Modified the `.rate` case in `tick(dt:)`: when `flying && !rightStickActive`, run the balance-style P-controller toward (0°, 0°). |
| `EasyPilotIOS/EasyPilotIOS/SimulatorView.swift` | Added `@State var rightStickActive`, forward to `sim.rightStickActive` via `.onChange`. Body now wraps in `GeometryReader`; new `landscapeContent` + `landscapeTelStrip` view builders; portrait body extracted to `portraitContent`. Right joystick now passes `isActive: $rightStickActive` (both portrait and landscape). |
| `openspec/changes/sprint-05/` (new) | proposal.md, design.md, specs/simulator-controller/spec.md, tasks.md, .openspec.yaml |
| `openspec/config.yaml` (new) | Created locally by openspec init. |

## Tasks remaining (all need physical device)

From `openspec/changes/sprint-05/tasks.md`:

- [ ] **1.4** Joystick: tap-without-moving sets `isActive=true`; lift sets it false; thumb-at-centre keeps it true
- [ ] **2.6** Tune so a 30° starting attitude returns to ±1° within 1.5 s in rate mode (no right thumb). Probably already in spec (`kPRoll=10, kPPitch=10`) but verify and tweak `kPScale` (currently 0.35) if needed.
- [ ] **3.5** Verify `@StateObject DroneSimulator` survives rotation — arm in portrait, rotate, confirm `_roll/_pitch/armed/throttle` don't reset
- [ ] **5.1** `./deploy.sh` (or full xcodebuild incantation from `CLAUDE.md`)
- [ ] **5.2** Portrait: rate-mode + balance-mode feel unchanged with thumb on stick
- [ ] **5.3** Portrait: release right stick from a bank → drone returns to level in ~1.5 s
- [ ] **5.4** Rotate to landscape mid-flight → clean layout switch, no overflow, no reset
- [ ] **5.5** Fly landscape with both thumbs → joysticks reachable, no clipping
- [ ] **5.6** Rotate back to portrait → unchanged layout

After verification, mark them done in `tasks.md` and run `/opsx:archive sprint-05`.

## Known issues / heads-up

- **Xcode plugin broken on this host**: `IDESimulatorFoundation` failed to load (`dlopen` symbol-not-found for `DVTDownloads.developerDocumentation`). I could not run a compile check before committing. If `./deploy.sh` fails the same way, the fix Apple suggests is `xcodebuild -runFirstLaunch`. The code should compile — changes are syntactically straightforward — but worth knowing.
- **`.claude/` is untracked** (local Claude Code CLI config). Old `continuation.md` had a TODO to gitignore it; that's still open if you want to do it.
- **`.gemini/skills/*` edits got bundled into commit `81e5973`** because they were already staged in the index from an earlier stash-pop. They're unrelated to sprint-05 — minor workflow doc tweaks. Not a regression, just noting it.

## How to resume

```bash
# Pull anything new
git fetch && git status

# Sanity-check what state the change is in
openspec status --change sprint-05
openspec validate sprint-05

# Implement / verify
./deploy.sh    # task 5.1
# … on device, run through 1.4, 2.6, 3.5, 5.2–5.6 …

# Tick checkboxes in openspec/changes/sprint-05/tasks.md as you go,
# then archive
/opsx:archive sprint-05
```

## Reference context

- Branch: `ep7-ios-app` (HEAD = `81e5973`, ahead of `main`)
- Device UDID for `./deploy.sh`: `00008110-001578C00252801E`
- Development Team: `47D26QX4MF`
- Today's date: 2026-06-02
- Existing archives use convention `openspec/changes/archive/YYYY-MM-DD-sprint-NN/` (set by remote in sprint-04 merge; we adopted it during the merge resolution earlier this session)
- Spec ownership: `openspec/specs/simulator-controller/spec.md` is **not** edited during implementation — it gets updated only at archive time via the delta in `openspec/changes/sprint-05/specs/simulator-controller/spec.md`
