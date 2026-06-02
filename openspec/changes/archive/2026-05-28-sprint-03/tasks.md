# Tasks: Sprint 3 - iPhone Sensors & Hybrid Connection

## Status Tracking
- [x] Phase 1: Preparation (OpenSpec Documentation)
- [x] Phase 2: iOS Motion Sensing (CoreMotion)
- [x] Phase 3: Hybrid Connectivity (Local vs. Ngrok)
- [x] Phase 4: One-Click Deployment Script

---

## Detailed Task List

### Phase 1: Preparation
- [x] Create Sprint 3 Proposal
- [x] Create Interaction Specifications
- [x] Move guidelines.md to OpenSpec
- [x] Clean up .gitignore for Xcode/PlatformIO

### Phase 2: iOS Motion Sensing
- [x] Add `CoreMotion` framework to the Xcode project.
- [x] Implement `MotionManager` class to read pitch/roll.
- [x] Add a visual tilt-indicator to `DashboardView.swift`.
- [x] Implement "Safe Test Mode" logic (trigger on 45° tilt).
  - UI overlay appears when |pitch| > 45° or |roll| > 45°.
  - When in local mode, sends UDP "SAFE_TEST" to ESP32 port 4243 (debounced, 2s).
  - ESP32 sets M1 = 1050 PWM for 500 ms then resets to 1000.

### Phase 3: Hybrid Connectivity
- [x] Implement local network probing in `ConnectionManager`.
  - ESP32 embeds its IP in every telemetry JSON packet (`esp32_ip` field).
  - `UDPListener` extracts and publishes `esp32IP` from telemetry.
  - `ConnectionManager.updateESP32IP()` compares first 3 octets of ESP32 IP
    against iPhone's `en0` (WiFi) address to set `isLocal`.
- [x] iOS shows LOCAL / RELAY badge in dashboard header.
- [x] Commands (SAFE_TEST) sent via UDP only when `isLocal == true`.
- [x] ESP32 updated to broadcast UDP directly on port 4242 (local path)
      in addition to the existing Ngrok WebSocket relay (remote path).
- [x] ESP32 listens for UDP commands on port 4243.

### Phase 4: Deployment
- [x] Create `deploy.sh` script in root directory.
  - Auto-detects first connected iPhone via `xcrun xctrace list devices`.
  - Accepts optional UDID argument: `./deploy.sh <UDID>`.
  - Uses `xcrun devicectl` (Xcode 15+) with fallback to `ios-deploy`.
  - Run: `./deploy.sh` from project root with iPhone connected via USB.
