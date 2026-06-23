# Proposal: Sprint 3 - iPhone Sensors & Hybrid Connection

## Goal
As a developer, I want to use my iPhone's motion sensors to interact with the drone safely and have a flexible connection that works both locally (direct) and remotely (Ngrok) without manual code changes. I also want a faster way to deploy the app to my physical iPhone.

## Acceptance Criteria
* **iPhone Motion Sensing:** The iOS app reads gyro/accelerometer data and visualizes the iPhone's own orientation in the UI.
* **Safe Interaction:** Tilting the iPhone triggers a "Safe Test Mode" (e.g., low-power motor pulse or UI alert) instead of full flight control.
* **Hybrid Connection Logic:** 
    * The app automatically detects if the ESP32 is reachable locally.
    * If local: Connect directly via WebSocket.
    * If remote: Use the Ngrok relay.
* **One-Click Deployment:** A script exists on the Mac Mini to build and install the app on the connected iPhone via USB.
* **Safety First:** Motors cannot be fully armed or throttled via tilt to prevent accidents.
