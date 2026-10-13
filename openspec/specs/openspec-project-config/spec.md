## Purpose

OpenSpec project configuration for EasyPilot: the `config.yaml` context and per-artifact rules that govern how proposals, specs and tasks are written, and the link to the requirements document `spec/fsd.md` (FSD §14).

## Requirements

### Requirement: Config contains project context

`openspec/config.yaml` SHALL contain a `context` block with the tech stack, the domain (phase 1 drone control, phase 2 simulation), key domain terms, roles and language rules.

`status: implemented`

#### Scenario: Context block present
- **WHEN** `openspec/config.yaml` is read
- **THEN** it contains `context:` naming ESP32/Arduino, Swift, Quarkus, Python, React/three.js, Kubernetes, the flight modes and the roles Pilot:in, Nutzer:in, Entwickler:in, Betreuer:in

### Requirement: Config contains per-artifact rules

`openspec/config.yaml` SHALL contain `rules` for `proposal` (FSD section references), `specs` (status marker per requirement, one capability per file) and `tasks` (`[GAP]` / `[SPEC]` labels).

`status: implemented`

#### Scenario: Rules block present
- **WHEN** `openspec/config.yaml` is read
- **THEN** `rules.proposal`, `rules.specs` and `rules.tasks` are present with these constraints

### Requirement: Specs note implementation status

Every requirement in every spec file SHALL include one of the markers `implemented`, `partial` or `not-implemented`.

`status: implemented`

#### Scenario: Gap analysis
- **WHEN** a reader looks for open work
- **THEN** all `partial` and `not-implemented` requirements can be found with `grep -rn "status: \(partial\|not-implemented\)" openspec/specs`

### Requirement: All artifacts validate

`openspec validate --all` SHALL pass for every spec and active change.

`status: implemented`

#### Scenario: Validation
- **WHEN** `openspec validate --all` runs
- **THEN** it reports no failures

#### Scenario: Pull request
- **WHEN** a pull request changes `openspec/` or `spec/`
- **THEN** the OpenSpec workflow validates all specs and changes
