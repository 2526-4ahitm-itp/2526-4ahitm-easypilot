## MODIFIED Requirements

### Requirement: Web simulator tests

The physics and control code of the web simulator SHALL have unit tests once it exists (§13, §10.2).

`status: implemented`

#### Scenario: Physics step
- **WHEN** CI runs
- **THEN** a test checks that a drone without thrust falls at about 9.81 m/s²

#### Scenario: Hover controller
- **WHEN** CI runs
- **THEN** the ported closed-loop hover tests pass
