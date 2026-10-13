---
title: Relay starten
weight: 4
---

Das Relay läuft auf einem Laptop im WLAN der Drohne.

## Nur im LAN

```bash
cd webinterface/backend/src/main/python
pip install websockets pyserial
python3 relay_server.py
```

Es nimmt WebSocket-Verbindungen auf Port 8080 an und schickt jede Nachricht als UDP-Broadcast auf
Port 4242 weiter. `LOG_LEVEL=DEBUG` zeigt jede Nachricht.

## Von außen über Ngrok

```bash
./start_system.sh
```

Das Skript startet einen Ngrok-Tunnel auf Port 8080, gibt die öffentliche URL aus (die gehört in
die ESP32-Firmware) und startet danach das Relay. Voraussetzung: Ngrok ist installiert und mit
einem Authtoken eingerichtet.

## MSP-Sender für den Web-Viewer

```bash
python3 websocket_sender.py
```

Liest den Flight Controller per USB-Serial und stellt die Lage auf `ws://localhost:8765` bereit.
