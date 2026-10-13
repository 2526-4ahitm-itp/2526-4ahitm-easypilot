# OpenSpec bei EasyPilot

OpenSpec hält fest, *was* EasyPilot können muss, und wie weit das umgesetzt ist.
Die fachliche Grundlage ist das Pflichtenheft [`spec/fsd.md`](../spec/fsd.md). Specs und
Changes verweisen darauf mit `§N.M`.

## Aufbau

```
openspec/
├── config.yaml          Projektkontext und Regeln für alle Artefakte
├── specs/               aktueller Stand, eine Capability pro Ordner
│   └── <capability>/spec.md
└── changes/
    ├── <datum>-<thema>/     offene Arbeit: proposal, design, tasks, Delta-Specs
    └── archive/             abgeschlossene Changes (Sprints, Coaching, Baseline)
```

Jede Requirement in `specs/` hat einen Status:
- `status: implemented`: im Code vorhanden, geprüft
- `status: partial`: teilweise vorhanden, der Grund steht im Szenario
- `status: not-implemented`: noch offen

Alles Offene auf einen Blick:

```bash
grep -rn "status: \(partial\|not-implemented\)" openspec/specs
```

## Capabilities

| Bereich | Specs |
|---|---|
| Drohne (Phase 1) | `hardware-platform`, `drone-discovery`, `command-protocol`, `telemetry-stream`, `fc-msp-bridge`, `flight-modes`, `safety-failsafe`, `standalone-web-firmware` |
| iOS-App | `ios-dashboard`, `ios-algorithms`, `ios-flight-simulator`, `ios-live-control` |
| Web und Python | `web-viewer`, `telemetry-relay`, `backend-api` |
| Phase 2 | `web-simulator`, `liftoff-hover` |
| Plattform und Prozess | `cloud-deployment`, `ci-testing`, `project-documentation`, `openspec-project-config` |

## Ablauf für eine Änderung

1. **Change anlegen:** `openspec new change <datum>-<thema>` oder den Ordner von Hand anlegen.
   In `proposal.md` stehen das Warum und das Was, mit Verweisen auf `§N.M`.
2. **Delta-Specs schreiben:** Unter `changes/<name>/specs/<capability>/spec.md` stehen nur die
   Unterschiede, als `## ADDED`, `## MODIFIED` oder `## REMOVED Requirements`. Eine geänderte
   Requirement wird komplett wiederholt, mit dem neuen Status.
3. **Tasks:** `tasks.md` mit Checkboxen. `[GAP]` heißt: setzt eine noch fehlende FSD-Anforderung
   um. `[SPEC]` heißt: nur Spec-Arbeit.
4. **Prüfen:** `openspec validate --all` muss grün sein.
5. **Archivieren:** Wenn alles umgesetzt ist, `openspec archive <name>`. Die Deltas wandern dann
   in `specs/`, und der Ordner kommt nach `changes/archive/`.

## Offene Changes

- `2026-10-13-phase2-web-simulator`: Web-Simulator mit Physik, Steuerung, Flugmodi, HUD und Deployment
- `2026-10-13-fix-ios-rc-mode`: RC-Modus in der App richtig anzeigen, STOP-Button, typisierte RC-Befehle
