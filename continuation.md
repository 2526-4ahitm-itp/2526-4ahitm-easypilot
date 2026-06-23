# Continuation Notes — EasyPilotIOS Simulator Fix & Project Cleanup

## Session Date
2026-05-28

## What Was Done This Session

### 1. iOS App Deployment (2x)
- Successfully built and deployed `EasyPilotIOS` to iPhone 13 Pro Max (`00008110-001578C00252801E`, "Sim")
- Build completed with Xcode 17C529 / iOS 26.2 SDK

### 2. Simulator Physics Fix — COMPLETED
**File:** `EasyPilotIOS/EasyPilotIOS/DroneSimulator.swift`

Rewrote world-space position physics from a decoupled vertical/horizontal model to proper thrust-vector decomposition:
- **Before:** horizontal acceleration was constant regardless of throttle (`pFrac * maxHorizAccel`)
- **Before:** vertical thrust ignored tilt, so drone could bank 80° without losing altitude
- **After:** `vertThrust = thrust * cos(pitch) * cos(roll)`, `fwdThrust = thrust * sin(pitchRad)`, `latThrust = thrust * sin(rollRad)`
- **After:** frame-rate independent drag via `pow(drag, dt * 60.0)`

Also removed unused `maxHorizAccel` constant.

### 3. Dashboard Roll Sign Fix — COMPLETED
**File:** `EasyPilotIOS/EasyPilotIOS/DashboardView.swift`
- Fixed telemetry 3D drone preview roll rotation from `data.roll * r` to `-data.roll * r` to match correct SceneKit convention

### 4. Project Cleanup — COMPLETED
- **`.claude/`** — left tracked in git (user wants it on other devices)
- **`openspec/`** — archived completed sprints 02–04 to `openspec/changes/archive/2026-05-28-sprint-{02,03,04}/`
  - Synced simulator-controller delta spec to `openspec/specs/simulator-controller/spec.md`
- **`.gemini/`** — removed duplicate `commands/opsx/*.toml` files, kept `skills/` folder

### 5. Git Commit & Push — COMPLETED
- Commit `aea6206` on branch `ep7-ios-app`
- Pushed to origin

## Current State of Modified Files
- `EasyPilotIOS/EasyPilotIOS/DroneSimulator.swift` — physics rewritten
- `EasyPilotIOS/EasyPilotIOS/DashboardView.swift` — roll sign fixed
- `EasyPilotIOS/EasyPilotIOS/ContentView.swift` — pre-existing changes (committed)
- `EasyPilotIOS/EasyPilotIOS/SimulatorScene.swift` — pre-existing changes (committed)
- `EasyPilotIOS/EasyPilotIOS/SimulatorView.swift` — pre-existing changes (committed)
- `PlatformIO/Projects/EasyPilotIOS/src/main.cpp` — pre-existing changes (committed)

## Next Steps / Open Items
- Simulator physics now uses realistic thrust-vector model — test fly to verify feel
- No known remaining bugs in simulator movement
- Consider updating continuation.md or deleting it once session continuity is no longer needed
