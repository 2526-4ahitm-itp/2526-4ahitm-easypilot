# Continuation Notes — Sprint 5 Wrap-Up & OpenSpec Expansion

## Session Date
2026-06-23

## Branch / Push State
- Branch: `ep7-ios-app`
- Latest pushed commit: `59ae158`
- Up to date with `origin/ep7-ios-app`
- Working tree clean

## What Was Done This Session

### 1. POSHOLD (Loiter) Flight Mode — COMPLETED
**File:** `EasyPilotIOS/EasyPilotIOS/DroneSimulator.swift`

Added a third `SimFlightMode.poshold` case ("POS") that uses real
physics on top of the existing P-controller theory — no velocity
damping cheats.

- Captures world-frame position (`_holdPosX`, `_holdPosZ`) on right-stick
  release, clears it whenever the stick is held again.
- Body-frame transform: yaw rotation matrix maps world velocity and
  position error into forward/right components.
- Position-PD + velocity-PD + accel-D produces a target tilt, applied
  through the existing attitude loop with `attResp` damping.
- Final tuned gains: `kPP=2.0`, `kVP=3.0`, `kVD=0.6`, `maxTilt=14°`,
  `attResp=1.0`. Earlier iteration (kPP=6, attResp=2.5) was too
  snappy — these gentler values give a realistic GPS-loiter feel.
- Horizontal velocity brake (added when fixing altitude-hold drift) is
  skipped in POSHOLD so the real counter-tilt physics aren't fought.
- `resetPhysics()` clears `_lastVFwdBody/Right` and `_hasHoldPos`.

### 2. Joystick Stabilization Indicator — COMPLETED
**Files:** `VirtualJoystick.swift`, `SimulatorView.swift`

- `VirtualJoystick` now takes `stabilizationActive: Bool`. Thumb fill
  + shadow switch to `EasyPilotTheme.success` (green) with a 0.2 s
  ease-in-out animation when true.
- Both portrait and landscape call sites updated:
  - **Left stick** (throttle/yaw): green whenever `!leftTouching`
  - **Right stick** (pitch/roll): green when
    `!rightTouching && (flightMode == .balance || flightMode == .poshold)`
- `floatingJoystick` helper signature gained `stabilizationActive:`.
- Default of `autopilotSticks` flipped to `true` so the autopilot
  visualisation is on out of the box.

### 3. OpenSpec Whole-Project Documentation — COMPLETED
**Goal:** OpenSpec was iOS-focused. Expanded to cover the whole project
so future sprints in any subsystem have a clear spec to start from.
No code changes — docs only.

New files:
- `openspec/README.md` — sprint workflow how-to and folder map
- `openspec/specs/firmware/spec.md` — ESP32 flight modes, MSP, watchdogs
- `openspec/specs/communication/spec.md` — UDP beacon + WebSocket + MSP
- `openspec/specs/dashboard/spec.md` — iOS Dashboard tab contract
- `openspec/specs/hardware/spec.md` — ESP32-C3, FC wiring, ESC PWM, battery
- `openspec/templates/sprint-proposal.md` — reusable proposal template
- `openspec/templates/sprint-tasks.md` — reusable tasks template

Rewritten:
- `openspec/specs/core/spec.md` — whole-project architecture, ASCII
  system map, subsystem-spec index, fail-safe-by-default requirement,
  reproducible-build requirement.

Unchanged:
- `openspec/specs/simulator-controller/spec.md`
- `openspec/specs/drone-telemetry/spec.md`
- `openspec/specs/guidelines.md`

### 4. Commits & Push — COMPLETED
- `e0d12f9` feat(sim): add POSHOLD loiter mode + green stabilization sticks
- `59ae158` docs(openspec): expand specs to whole-project + add workflow scaffolding
- Pushed `63651e1..59ae158` to `origin/ep7-ios-app`
- **No `Co-Authored-By` trailer** in either commit (sole committer: simoneder)

## Earlier in This Conversation (Pre-Compaction)

The full conversation also covered:
- Landscape UI redesign with collapsible chip + autopilot-sticks toggle
- Fixed broken altitude-hold (replaced fake "last commanded throttle"
  with real PID using `hoverT = gravity/maxThrust` and tilt
  compensation `1/cos(pitch)cos(roll)`)
- Added horizontal velocity brake on stick release (skipped in POSHOLD)
- Merged `origin/main` into `ep7-ios-app`, took main's newer firmware
  for the `main.py` conflict (`git checkout --theirs`)
- Opened a PR via `gh` (had to `brew install gh` first; user did
  `gh auth login` manually)
- Settings persistence + throttle re-grab smoothing
- iOS app built and deployed via `xcodebuild` + `ios-deploy`

## Open Items / Next Steps

1. **POSHOLD tuning verification** — the gentler gains
   (kPP=2, kVP=3, kVD=0.6, maxTilt=14, attResp=1) need a real flight-feel
   check. If it feels too floaty, bump `kPP` to 2.5–3 first.
2. **Sprint 6 — Live mode** — was pushed from Sprint 5. Real-drone
   "Live" tab equivalent of the simulator (joysticks send `RC` packets
   over WebSocket). Firmware already supports `MODE_RC` and `RC` packets;
   iOS side needs the screen.
3. **Folding sprint-05 delta spec into live specs** — when Sprint 5 is
   officially closed, fold
   `openspec/changes/2026-06-23-sprint-05-landscape-ui/specs/` into
   `openspec/specs/simulator-controller/spec.md` and move the sprint
   folder to `openspec/changes/archive/`.
4. **PR status** — a PR was opened earlier in the conversation; check
   `gh pr status` or the GitHub UI to see if it's still open and ready
   for review, or if it needs a fresh PR for the new commits.

## House Rules (Saved in Memory, Reproduced Here for Convenience)

- **Never push without asking** (this session the user explicitly asked).
- **No `Co-Authored-By: Claude` trailer** in commits — user is sole committer.
- **OpenSpec first** for new features: write the proposal/spec delta
  before code.
- **Follow `guidelines.md`** in `openspec/specs/`.
