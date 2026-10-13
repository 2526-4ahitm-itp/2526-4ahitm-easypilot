## Purpose

Automated tests and continuous integration for every subsystem with logic (FSD §13). All workflows live in `.github/workflows/` and run without secrets, so they also work for pull requests.

## Requirements

### Requirement: iOS unit and UI tests

The iOS app SHALL have unit tests for the command wire format, telemetry decoding, Sound Mode math and profile persistence, plus a UI smoke test of the three tabs, run in the iOS simulator on CI (§13).

`status: implemented`

#### Scenario: iOS workflow
- **WHEN** a pull request changes `EasyPilotIOS/`
- **THEN** the iOS workflow runs `xcodebuild test` without code signing

### Requirement: Backend, frontend and simulator workflows

Backend tests (`./mvnw -B test`), frontend lint and build, and the Liftoff hover tests (`python -m unittest`) SHALL each run in their own workflow on pushes to `main` and on pull requests that touch their folder (§13).

`status: implemented`

#### Scenario: Path filter
- **WHEN** a pull request only changes `simulator/`
- **THEN** only the Simulator workflow runs

### Requirement: No secrets for tests

No test workflow SHALL need repository secrets; only the image push uses `GITHUB_TOKEN` and only on `main` (§13).

`status: implemented`

#### Scenario: Pull request from a branch
- **WHEN** a pull request is opened
- **THEN** all test workflows can run without access to secrets

### Requirement: Firmware and Python helper tests

The ESP32 firmware logic and the Python relay SHALL have automated tests (§13).

`status: not-implemented`

#### Scenario: Firmware logic
- **WHEN** CI runs
- **THEN** MSP parsing and command handling are tested natively (no such tests yet)

### Requirement: Web simulator tests

The physics and control code of the web simulator SHALL have unit tests once it exists (§13, §10.2).

`status: not-implemented`

#### Scenario: Physics step
- **WHEN** CI runs
- **THEN** a test checks that a drone without thrust falls at about 9.81 m/s²
