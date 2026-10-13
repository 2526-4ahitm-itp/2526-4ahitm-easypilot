## MODIFIED Requirements

### Requirement: Flight mode mapping

The app SHALL map the `mode` string to its flight mode enum and fall back to IDLE for unknown or missing values; every mode the firmware reports SHALL map to a real case (§5.3, §6).

`status: implemented`

#### Scenario: Unknown mode
- **WHEN** `mode` is missing or `"foo"`
- **THEN** the app shows IDLE and does not crash

#### Scenario: RC mode reported
- **WHEN** the firmware reports `"mode":"RC"`
- **THEN** the app shows RC
