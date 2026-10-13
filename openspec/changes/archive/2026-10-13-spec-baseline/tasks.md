## 1. Requirements document

- [x] 1.1 [SPEC] Write `spec/fsd.md` (Pflichtenheft phase 1 + phase 2) with numbered sections

## 2. OpenSpec configuration

- [x] 2.1 [SPEC] Add context and rules to `openspec/config.yaml`

## 3. Capability specs

- [x] 3.1 [SPEC] Drone side: `hardware-platform`, `drone-discovery`, `command-protocol`, `telemetry-stream`, `fc-msp-bridge`, `flight-modes`, `safety-failsafe`
- [x] 3.2 [SPEC] iOS: `ios-dashboard`, `ios-algorithms`, `ios-flight-simulator`, `ios-live-control`
- [x] 3.3 [SPEC] Other phase 1 parts: `standalone-web-firmware`, `telemetry-relay`, `web-viewer`
- [x] 3.4 [SPEC] Phase 2: `web-simulator`, `liftoff-hover`
- [x] 3.5 [SPEC] Platform: `backend-api`, `cloud-deployment`, `ci-testing`, `project-documentation`, `openspec-project-config`
- [x] 3.6 [SPEC] Verify every status marker against the code
- [x] 3.7 [SPEC] Remove the old specs `core`, `communication`, `firmware`, `hardware`, `dashboard`, `simulator-controller`, `drone-telemetry`, `guidelines.md`

## 4. Changes

- [x] 4.1 [SPEC] Archive `sprint-05`, `2026-06-23-sprint-05-landscape-ui`, `2026-10-12-coaching-r1`
- [x] 4.2 [SPEC] Open `2026-10-13-phase2-web-simulator` and `2026-10-13-fix-ios-rc-mode`

## 5. Verification

- [x] 5.1 [SPEC] `openspec validate --all` passes
