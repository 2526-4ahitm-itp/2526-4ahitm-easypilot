## Why

The OpenSpec of EasyPilot did not reflect the project. `openspec validate --all` failed for 8 of 10 items: the main specs used delta headers (`## ADDED Requirements`) instead of `## Purpose` / `## Requirements`, so the tool could not see a single requirement. Specs were scoped per iOS tab instead of per capability, carried no implementation status, and partly contradicted the code (motor numbering, battery warning „deferred“ although implemented, Sound Mode placed in the Dashboard). There was no requirements document to reference, and phase 2 (simulation, since 2026-09-14, FSD §1.2/§1.3) was missing entirely.

## What Changes

- Add `spec/fsd.md`, the Pflichtenheft for phase 1 and phase 2, with numbered sections that specs and proposals reference as `§N.M`.
- Fill `openspec/config.yaml` with project context and per-artifact rules (status markers, `[GAP]`/`[SPEC]` labels, FSD references).
- Replace the seven old specs and `guidelines.md` with 21 capability specs in the canonical format, each requirement with `status: implemented | partial | not-implemented`, verified against the code on 2026-10-13.
- Add specs for phase 2: `web-simulator` (target, not implemented), `liftoff-hover` (prototype, implemented) and for the parts that had none: `telemetry-relay`, `web-viewer`, `backend-api`, `cloud-deployment`, `ci-testing`, `project-documentation`, `standalone-web-firmware`.
- Archive the finished changes `sprint-05`, `2026-06-23-sprint-05-landscape-ui` and `2026-10-12-coaching-r1`.
- Open the follow-up changes `2026-10-13-phase2-web-simulator` and `2026-10-13-fix-ios-rc-mode` for the open work.

## Capabilities

### New Capabilities
- `hardware-platform`, `drone-discovery`, `command-protocol`, `telemetry-stream`, `fc-msp-bridge`, `flight-modes`, `safety-failsafe` (phase 1 drone side, §4–§7)
- `ios-dashboard`, `ios-algorithms`, `ios-flight-simulator`, `ios-live-control` (§8)
- `standalone-web-firmware` (§9), `telemetry-relay` (§5.5), `web-viewer` (§10.1)
- `web-simulator` (§10.2), `liftoff-hover` (§11)
- `backend-api` (§12.1), `cloud-deployment` (§12.2), `ci-testing` (§13)
- `project-documentation` (§14), `openspec-project-config`

### Removed Capabilities
- `core`, `communication`, `firmware`, `hardware`, `dashboard`, `simulator-controller`, `drone-telemetry`, `guidelines.md`: content moved into the capabilities above.

## Impact

- Docs only, no code changes.
- `CLAUDE.md`, `README.adoc` and the Hugo reference page point to the new spec names.
