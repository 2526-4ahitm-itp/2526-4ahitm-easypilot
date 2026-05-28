# Continuation Notes — EasyPilotIOS Simulator Fix & Project Cleanup

## Session Date
2026-05-28

## What Was Done

### 1. iOS App Deployment
- Successfully built and deployed `EasyPilotIOS` to iPhone 13 Pro Max (`00008110-001578C00252801E`, "Sim")
- Build completed with Xcode 17C529 / iOS 26.2 SDK
- App installed and running on device

### 2. Cleanup Assessment (Completed)
Analyzed `.claude/`, `.gemini/`, and `openspec/` directories. Findings and recommended actions below.

#### `.claude/`
- Contains only `.claude/settings.local.json` (local IDE config)
- **Action:** Add `.claude/` to `.gitignore` or delete the directory

#### `.gemini/`
- Contains duplicate definitions:
  - `.gemini/commands/opsx/*.toml` (4 command files)
  - `.gemini/skills/*/SKILL.md` (4 skill files)
- Content is essentially identical between TOML commands and SKILL.md files
- **Action:** Choose one format (commands OR skills), delete the other. Decide if these should be tracked or fully gitignored.

#### `openspec/`
- **Sprints 2, 3, and 4 are 100% complete** — all task checkboxes are `[x]`
- Sprint 2 uses `specs.md`, Sprints 3 & 4 use `tasks.md` (inconsistent structure)
- Sprint 2 and 4 have delta specs under `changes/<sprint>/specs/` that should be verified as synced to `openspec/specs/` before archiving
- **Action:** Archive completed sprints to `openspec/changes/archive/YYYY-MM-DD-<sprint-name>/`

### 3. Simulator / Drone Movement (IN PROGRESS — NOT COMPLETED)
- User reported: **simulator isn't moving the drone entirely correctly**
- The explore agent failed during codebase analysis
- **Still needed:** Deep dive into EasyPilotIOS source code to find:
  - Drone simulation logic
  - Movement/physics calculations
  - Joystick/control input handling
  - SceneKit / 3D model movement code
  - Any frame-rate or coordinate system bugs

## Next Steps for Next Session

### Priority 1: Fix Drone Movement
1. Re-run exploration of `EasyPilotIOS/` with a working agent or manual file reads
2. Focus on:
   - Any `Simulator*` or `Drone*` Swift files
   - SceneKit node transforms / position updates
   - Input-to-movement mapping (accelerometer, gyro, touch joysticks)
   - Delta time usage (`dt`) in movement calculations
   - Coordinate system mismatches (SceneKit Y-up vs drone's reference frame)
3. Identify the bug and propose fix before applying (user requested to be told about major changes)

### Priority 2: Project Cleanup
1. **`.claude/`** → add to `.gitignore`
2. **`openspec/`** → archive completed sprints 02–04
3. **`.gemini/`** → deduplicate commands/skills

## Context for Next Agent
- This is a Quarkus + iOS + webinterface project
- iOS app uses SceneKit with GLTFSceneKit package (v0.4.1)
- Drone model: `drohne-compressed.usdz`
- Deployment script: `./deploy.sh [UDID]` (default UDID is `00008110-001578C00252801E`)
- Development Team: `47D26QX4MF`
