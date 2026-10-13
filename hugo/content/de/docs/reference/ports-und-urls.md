---
title: Ports und URLs
weight: 6
---

## Im WLAN der Drohne

| Port | Protokoll | Wer | Wofür |
|---|---|---|---|
| 81 | WebSocket | ESP32 (Companion) | Befehle und Telemetrie |
| 4242 | UDP-Broadcast | ESP32, Relay → App | Beacon `EASYPILOT:<IP>`, Relay-Telemetrie |
| 80 | HTTP | ESP32 (Standalone) | Web-Dashboard, `/heartbeat`, `/start_time`, `/start_acc` |
| 8080 | WebSocket | Relay | Telemetrie annehmen |
| 8765 | WebSocket | MSP-Sender | Lage für den Web-Viewer |

## Lokal am Entwickler-PC

| Port | Wofür |
|---|---|
| 8080 | Quarkus Dev-Mode (`/api/status`) |
| 5173 | Vite Dev-Server (Web-Viewer) |
| 1313 | Hugo Dev-Server (diese Doku) |
| 9001 (UDP) | Liftoff-Telemetrie → Liftoff-Hover |

## Öffentlich

| URL | Was | Stand |
|---|---|---|
| https://2526-4ahitm-itp.github.io/2526-4ahitm-easypilot/ | diese Doku | live nach Merge |
| https://it220234.cloud.htl-leonding.ac.at/ | Web-Simulator | vorbereitet, nicht deployt |
| https://it220234.cloud.htl-leonding.ac.at/api/status | Backend | vorbereitet, nicht deployt |
| `ghcr.io/2526-4ahitm-itp/easypilot-backend`, `…/easypilot-web` | Images | öffentlich |
