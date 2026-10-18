## ADDED Requirements

### Requirement: GPS target input

The user SHALL be able to enter a GPS coordinate, which the autopilot converts to simulator metres through a fixed reference point using a local east-north-up frame (§20.4, US-13).

`status: implemented`

#### Scenario: Reference point
- **WHEN** the GPS coordinate of the reference point is entered
- **THEN** the target is the simulator origin

### Requirement: Obstacle map

The autopilot SHALL build a 3D occupancy grid of the obstacles of the flight area (from the track file, or from the scene in the own web simulator) with a safety margin around every obstacle (§20.4).

`status: partial`

#### Scenario: Obstacle inflated
- **WHEN** an obstacle is added to the map
- **THEN** all grid cells within the safety margin around it are marked as blocked

### Requirement: Collision-free low-altitude flight to the target

The autopilot SHALL plan a path to the target that stays 1–3 m above ground and outside blocked cells, fly it, and replan when the local check finds an obstacle closer than the braking distance (§20.4, US-13).

`status: partial`

#### Scenario: Ten random targets
- **WHEN** 10 random reachable targets are flown at full allowed speed
- **THEN** there are 0 collisions and the altitude stays between 1 and 3 m

#### Scenario: Speed limited by braking distance
- **WHEN** free space ahead is shorter than the braking distance at the current speed
- **THEN** the autopilot slows down before continuing
