## Context

EasyPilot is brownfield: phase 1 (firmware, iOS app, relay, viewer) is done, phase 2 (simulation) has started with a Liftoff prototype. The old specs were written sprint by sprint around iOS tabs. This change rebuilds them as a baseline that describes the system as it is, with an explicit status per requirement, and the FSD as the target.

## Goals / Non-Goals

**Goals:**
- Every requirement visible to `openspec validate`, `list` and `archive`.
- One capability per spec file, named after what the system does, not after a screen.
- Honest status: verified in code, `partial` with the reason in the scenario.
- Phase 2 target captured so the remaining work can be planned as `[GAP]` tasks.

**Non-Goals:**
- Fixing any of the gaps (separate changes).
- Re-specifying archived sprint deltas; they stay as history.

## Decisions

- **Spec language English, docs German.** OpenSpec keywords (`SHALL`, `WHEN`/`THEN`) are English and the validator expects them; the same split is used by the Franklyn project of the class. Domain words (Pilot:in, Betreuer:in) stay German.
- **FSD in German under `spec/fsd.md`.** It is written for the team and the teacher; specs reference it with `§N.M` as required by `config.yaml`.
- **Status from code, not from old specs.** Every status was checked against the sources on 2026-10-13 (e.g. `batteryColor` in `DashboardView.swift` → battery warning `implemented`; `FlightMode` has no `rc` case → `partial`; manual IP not persisted → `partial`).
- **Hardware link marked `not-implemented`.** The Air Unit defect is the reason for phase 2; keeping it as an open requirement makes the dependency visible.
- **Sprint changes archived as they were.** Their delta format predates this baseline; they are history and are not validated.

## Risks / Trade-offs

- [Specs drift again] → the `openspec-project-config` spec requires `openspec validate --all` to pass, and the new OpenSpec workflow runs it on every pull request that touches `openspec/` or `spec/`.
- [Status markers get stale] → every follow-up change has to update the status of the requirements it touches when it is archived.
