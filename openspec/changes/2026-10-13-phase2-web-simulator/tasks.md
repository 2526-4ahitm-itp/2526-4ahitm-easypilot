## 1. Decisions

- [ ] 1.1 [SPEC] Team decides: own integrator or physics library; record the result in `design.md` (FSD §19)
- [ ] 1.2 [SPEC] Team adds the remaining phase 2 dates and milestones to the project page

## 2. Physics (§10.2, §15)

- [ ] 2.1 [GAP] Add a physics module (rigid body, four thrusts, gravity, drag, ground contact) with a fixed time step
- [ ] 2.2 [GAP] Unit tests: free fall ≈ 9.81 m/s², hover thrust balances gravity, identical path at 30 and 60 fps

## 3. Input (§10.2, US-08)

- [ ] 3.1 [GAP] Gamepad API input in Mode 2 with deadband and expo
- [ ] 3.2 [GAP] Keyboard fallback (W/S, A/D, arrows, H)

## 4. Flight modes (§10.2, §11, US-07)

- [ ] 4.1 [GAP] Rate mode (port from `DroneSimulator.swift`)
- [ ] 4.2 [GAP] Angle mode (P-controller levelling)
- [ ] 4.3 [GAP] Hover mode (port `HoverController` from `hover.py`)
- [ ] 4.4 [GAP] Port the closed-loop tests from `test_hover.py`

## 5. Scene and HUD (§10.2)

- [ ] 5.1 [GAP] Simulator route with ground, sky and chase/FPV camera, using `drohne-compressed.glb`
- [ ] 5.2 [GAP] HUD: height, speed, attitude, throttle, mode

## 6. Delivery (§12.2, US-08, US-09)

- [ ] 6.1 [GAP] Run the unit tests in the Frontend workflow
- [x] 6.2 [GAP] Deploy backend and web to namespace `student-it220270` and check `https://it220270.cloud.htl-leonding.ac.at/api/status`
- [ ] 6.3 [SPEC] Update status markers in `web-simulator`, `cloud-deployment`, `ci-testing` and archive this change
