# Proposal: Sprint 4 - Phone-Side Simulator & Controller Foundation

## Goal
As a pilot, I want a phone-side flight simulator that responds to virtual joystick inputs so I can practise control feel and tune expo/rate settings before flying the real drone. The existing "Control" tab is renamed to "Algorithms" to clarify its purpose (PID / balance tuning). A new "Simulator" tab is the primary deliverable; real drone control via the same joystick interface is deferred to Sprint 5.

## Context
FPV drones run Betaflight in **Rate/Acro mode** by default — stick deflection maps to angular *rate* (°/s), not a target angle. This makes them extremely sensitive near center compared to self-levelling quads. Industry-standard layout is **Mode 2**:
- Left stick: Throttle (Y, non-centering) · Yaw (X, self-centering)
- Right stick: Pitch (Y, self-centering) · Roll (X, self-centering)

Expo curves (common formula: `out = in³ · expo + in · (1–expo)`) reduce sensitivity near stick centre without limiting full-deflection authority — standard practice for FPV.

## Acceptance Criteria
* **Tab rename:** "Control" tab renamed to "Algorithms".
* **Simulator tab:** New "Simulator" tab added as the third tab.
* **Dual virtual joystick:** Mode 2 layout; throttle axis is non-centering (ratchet-free, stays where released); all other axes self-center.
* **Rate-mode physics:** Stick input drives angular rates; attitude integrates at configurable max rates (roll/pitch up to 360°/s, yaw up to 200°/s).
* **Expo:** Configurable expo factor (0.0–1.0) applied to all lateral axes via a slider.
* **Motor PWM simulation:** Motor bars show computed PWM (1000–2000) from throttle + attitude error mixing.
* **Attitude display:** Horizon indicator and roll/pitch/yaw values update in real time from simulated state.
* **Sim / Live toggle:** Pill toggle in header switches between Simulator and Live (real drone) modes. Live is visible but disabled ("Sprint 5") in this sprint.
* **Simulated arming:** Simulator requires an explicit "Arm Simulator" tap before physics run; "Disarm" resets attitude and stops motors.
* **No real commands sent:** Simulator mode never sends any WebSocket command to the drone.
