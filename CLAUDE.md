# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EasyPilot is a drone telemetry and control system consisting of multiple subsystems that communicate in a pipeline: **Betaflight Flight Controller → ESP32 → Python Relay → iOS App / Web Dashboard**.

The communication stack:
- **Flight Controller ↔ ESP32**: UART using MSP (MultiWii Serial Protocol)
- **ESP32 → Python Relay**: WebSocket over WLAN
- **Python Relay → Clients**: UDP broadcast (for iOS app) and WebSocket re-broadcast (for web)

## Subsystems and Commands

### Web Frontend (`webinterface/frontend/`)
```bash
npm run dev      # Start Vite dev server
npm run build    # Production build
npm run lint     # ESLint
npm run preview  # Preview production build
```

### Java Backend (`webinterface/backend/` / root `pom.xml`)
```bash
./mvnw quarkus:dev     # Start Quarkus in dev mode (hot reload)
./mvnw clean package   # Build JAR
./mvnw test            # Run tests
```

### Python Relay Server (`webinterface/backend/src/main/python/`)
```bash
python relay_server.py      # WebSocket relay (ESP32 → UDP broadcast)
python websocket_sender.py  # Test data sender
```

### iOS App (`EasyPilotIOS/`)
Open `EasyPilotIOS.xcodeproj` in Xcode and build/run via Xcode.

### API Tests (`api/`)
```bash
npm test    # httpyac: runs requests.http against dev environment
```

### Full System Startup
```bash
./start_system.sh   # Launches all backend services together
```

### ESP32 Firmware (`PlatformIO/Projects/EasyPilotIOS/`)
Use PlatformIO IDE or CLI (`pio run`, `pio upload`) to build and flash.
The active project is `PlatformIO/Projects/EasyPilotIOS/` (esp32-c3-supermini board).
WiFi credentials are in `secrets.ini` (not committed); `load_secrets.py` generates `secrets_auto.h`.

## Architecture

```
Betaflight FC (Nazgul DC5 ECO 6S)
        │ UART / MSP
        ▼
    ESP32 (WLAN bridge)
        │ WebSocket (WLAN)
        ▼
relay_server.py (Python)
    ├── UDP broadcast → iOS App (Swift/UIKit)
    └── WebSocket → Web Dashboard (React + Three.js)
```

**Key source locations:**
- `EasyPilotIOS/EasyPilotIOS/` — Swift source: `ConnectionManager.swift` (UDP/WebSocket), `DashboardView.swift` (telemetry UI with 3D model), motion sensor integration
- `webinterface/frontend/src/` — React pages (`HomePage.jsx`, `ModelPage.jsx`) and `components/Model.jsx` (Three.js 3D drone viewer using `public/models/drohne-compressed.glb`)
- `webinterface/backend/src/main/python/relay_server.py` — bridges ESP32 WebSocket stream to UDP broadcast
- `PlatformIO/src/` — ESP32 firmware reading MSP telemetry from flight controller
- `openspec/` — OpenAPI specs for the REST backend

## Technology Stack

| Layer | Technology |
|-------|-----------|
| iOS App | Swift, UIKit/SwiftUI, UDP sockets |
| Web UI | React 19, Vite, Three.js, @react-three/fiber, @react-three/drei |
| Backend API | Java 21, Quarkus 3.28 |
| Relay | Python 3, `websockets` library |
| Firmware | C++ / PlatformIO (ESP32) |
| Protocol | MSP (MultiWii Serial Protocol) over UART |

## Development Notes

- The iOS app receives telemetry via UDP broadcast; the web dashboard connects via WebSocket relay.
- The 3D drone model (`.glb` / `.usdz`) lives in `webinterface/frontend/public/models/` and is also bundled in the iOS app.
- MSP protocol parsing happens in the ESP32 firmware (`PlatformIO/`) and must match Betaflight's MSP message format.
- The `openspec/` directory tracks API contract changes — update it when REST endpoints change.
