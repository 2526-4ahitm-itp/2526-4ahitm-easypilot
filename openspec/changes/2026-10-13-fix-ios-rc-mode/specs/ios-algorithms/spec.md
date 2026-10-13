## MODIFIED Requirements

### Requirement: Stop button while a mode runs

The Algorithms tab SHALL show a STOP button whenever the firmware reports a mode other than IDLE (§8.2, §7.1).

`status: implemented`

#### Scenario: RC mode running
- **WHEN** the firmware reports `"mode":"RC"`
- **THEN** the STOP button is visible
