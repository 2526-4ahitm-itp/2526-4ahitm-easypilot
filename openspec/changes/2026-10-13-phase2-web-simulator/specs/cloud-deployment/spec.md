## MODIFIED Requirements

### Requirement: Running production deployment

Backend and web simulator SHALL be deployed and reachable at `https://it220234.cloud.htl-leonding.ac.at/` (§3.3, US-08, US-09).

`status: implemented`

#### Scenario: Status from outside
- **WHEN** `curl https://it220234.cloud.htl-leonding.ac.at/api/status` is run
- **THEN** it returns 200
