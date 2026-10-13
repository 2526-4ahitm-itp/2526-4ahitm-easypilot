## Purpose

The Quarkus backend in `webinterface/backend`. Today it only exposes a health/status endpoint used by the cloud readiness probe; further endpoints for the web simulator are an open point (FSD §12.1, US-09, §19).

## Requirements

### Requirement: Status endpoint

The backend SHALL answer `GET /api/status` with HTTP 200 (§12.1, US-09).

`status: implemented`

#### Scenario: Health check
- **WHEN** `GET /api/status` is called
- **THEN** the response status is 200

### Requirement: Tests on CI

The backend SHALL have Quarkus tests that run on every push and pull request (§13).

`status: implemented`

#### Scenario: Pull request
- **WHEN** a pull request changes `webinterface/backend`
- **THEN** the Backend workflow runs `./mvnw -B test`

### Requirement: Simulator data endpoints

If the web simulator stores data (e.g. best times or flight recordings), the backend SHALL provide the endpoints for it (§12.1, §19).

`status: not-implemented`

#### Scenario: Save flight
- **WHEN** the web simulator saves a flight
- **THEN** the backend persists it (scope still open)
