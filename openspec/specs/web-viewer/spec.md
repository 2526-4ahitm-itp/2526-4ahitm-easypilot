## Purpose

The existing React + three.js web viewer in `webinterface/frontend`: it shows the drone model in the browser and moves it with attitude data from a WebSocket. It is the starting point for the phase 2 web simulator (FSD §10.1).

## Requirements

### Requirement: 3D model in the browser

The viewer SHALL load `drohne-compressed.glb` with @react-three/fiber and render it on the `/model` route (§10.1).

`status: implemented`

#### Scenario: Open model page
- **WHEN** a browser opens `/model`
- **THEN** the drone model is rendered

### Requirement: Attitude from a WebSocket stream

The viewer SHALL apply roll, pitch and yaw from `attitude` messages and show m1/m4 from `motor_data` messages (§10.1, §5.5).

`status: partial`

#### Scenario: Stream available
- **WHEN** `attitude` messages arrive on the WebSocket
- **THEN** the model rotates accordingly (partial: the URL is hard-coded to `ws://localhost:8765`, so it only works on the developer laptop and not from the LeoCloud; the code notes that degrees may need converting to radians)

### Requirement: Lint and build on CI

The frontend SHALL pass `npm run lint` and `npm run build` on every push and pull request (§13).

`status: implemented`

#### Scenario: Pull request
- **WHEN** a pull request changes `webinterface/frontend`
- **THEN** the Frontend workflow runs lint and build
