## MODIFIED Requirements

### Requirement: Typed command builder in the app

The app SHALL build commands through the `DroneCommand` type instead of hand-written strings in views (§5.2).

`status: implemented`

#### Scenario: Views use DroneCommand
- **WHEN** a view sends a command
- **THEN** it uses `DroneCommand.payload`, including `START_RC` and `RC`
