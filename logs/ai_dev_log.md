# AI Development Log - EasyPilot Project

**Date:** October 26, 2023 (Current Session)
**Project Phase:** Sprint 1 - Dashboard & Telemetry
**Current Developer:** AI Assistant (Gemini)

## 1. Project Context
The goal is to create an iOS app (Swift) to control and monitor a drone (Nazgul DC5) via an ESP32.
- **Communication:** UDP Broadcast (Port 5000).
- **Data Format:** JSON `{"roll": float, "pitch": float, "yaw": float, "m1": int, "m4": int}`.
- **Hardware:** ESP32 connected to Flight Controller via UART (MSP protocol).

## 2. Current Implementation Status
We have implemented the core "Read-Only" telemetry stack for Sprint 1.

### Created Files (located in `EasyPilotIOS/EasyPilotIOS/`):
1.  **`DroneTelemetry.swift`**: 
    - `Codable` struct matching the ESP32 JSON output.
    - *Note:* Data types are `Float` for angles and `Int` for motors.

2.  **`UDPListener.swift`**:
    - Uses Apple's `Network` framework (`NWListener`).
    - Listens on UDP Port 5000.
    - Decodes JSON and publishes to `DashboardView`.
    - *Constraint:* UDP Broadcasts often fail in the iOS Simulator. Testing on a physical device is required.

3.  **`DashboardView.swift`**:
    - SwiftUI View.
    - Displays raw text data.
    - Includes a `SceneView` for 3D visualization.
    - *Logic:* Loads `drohne-compressed.glb` and applies rotation based on telemetry.

4.  **Documentation**:
    - `spezifikationen.txt`: Full project specs.
    - `sprint_1.txt`: Current sprint user story and acceptance criteria.

## 3. Critical Next Steps (Handover to next AI/User)

### A. Xcode Integration (User Action Required)
The files were created via file system operations. The user **must** manually add them to the Xcode project (`EasyPilotIOS.xcodeproj`).
- Add `DroneTelemetry.swift`, `UDPListener.swift`, `DashboardView.swift`.
- Add `webinterface/frontend/public/models/drohne-compressed.glb` to the App Bundle resources.

### B. Permissions
- **Info.plist**: The key `Privacy - Local Network Usage Description` (NSLocalNetworkUsageDescription) must be added. Without this, the UDP listener will fail silently or crash on a real device.

### C. 3D Rotation Logic (Refinement Needed)
The current rotation logic in `DashboardView.swift` is basic:
```swift
scene.rootNode.eulerAngles = SCNVector3(pitch, yaw, roll)
```
**Potential Issues to Debug:**
1.  **Units:** ESP32 `espsender.ino` sends radians (`random(-100, 100) / 100.0`). SceneKit expects Radians. *Status: Looks compatible.*
2.  **Axis Mapping:** Drone frames (NED - North East Down) often differ from SceneKit (Y-up).
    - If the drone spins like a top but the model rolls, swap the axes in the `SCNVector3`.
    - *Action:* Wait for user feedback on visual behavior, then adjust the vector mapping.

### D. Future Sprints
- **Configuration:** Implement sending data *back* to the ESP32 (TCP or UDP unicast) to adjust PID/Rates.
- **Flight Controller Integration:** The ESP32 currently sends simulated data (`espsender.ino`). The real UART/MSP implementation on the ESP32 side is pending.

## 4. File Locations
- **Specs:** `/spezifikationen.txt`
- **Sprint:** `/sprint_1.txt`
- **Source:** `/EasyPilotIOS/EasyPilotIOS/`
- **ESP32 Source:** `/espData/espsender.ino`
