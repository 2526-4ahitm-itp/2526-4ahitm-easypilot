# Tasks: Sprint 3 - iPhone Sensors & Hybrid Connection

## Status Tracking
- [ ] Phase 1: Preparation (OpenSpec Documentation)
- [ ] Phase 2: iOS Motion Sensing (CoreMotion)
- [ ] Phase 3: Hybrid Connectivity (Local vs. Ngrok)
- [ ] Phase 4: One-Click Deployment Script

---

## Detailed Task List

### Phase 1: Preparation
- [x] Create Sprint 3 Proposal
- [x] Create Interaction Specifications
- [x] Move guidelines.md to OpenSpec
- [x] Clean up .gitignore for Xcode/PlatformIO

### Phase 2: iOS Motion Sensing
- [ ] Add `CoreMotion` framework to the Xcode project.
- [ ] Implement `MotionManager` class to read pitch/roll.
- [ ] Add a visual tilt-indicator to `DashboardView.swift`.
- [ ] Implement "Safe Test Mode" logic (trigger on 45° tilt).

### Phase 3: Hybrid Connectivity
- [ ] Implement local network probing in `UDPListener` or a new `ConnectionManager`.
- [ ] Update Swift code to toggle between Local WebSocket and Ngrok WebSocket.
- [ ] Update ESP32 code to handle local WebSocket server requests.

### Phase 4: Deployment
- [ ] Create `deploy.sh` script in root directory.
- [ ] Verify script can build and install to USB-connected iPhone.
