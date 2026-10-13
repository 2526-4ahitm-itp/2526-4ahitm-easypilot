---
title: Kommunikation
weight: 3
---

Zwischen iPhone und Flight Controller liegen zwei Strecken:

```
iOS-App ⟷ WLAN (WebSocket + UDP) ⟷ ESP32-C3 ⟷ UART (MSP) ⟷ Betaflight-FC
```

{{< plantuml src="/content/de/diagrams/sequenz-verbindung.puml" />}}

## Warum ein UDP-Beacon?

Im Schul- oder Handy-Hotspot-WLAN bekommt der ESP32 jedes Mal eine andere IP. Statt sie
abzutippen, ruft der ESP32 alle 5 s `EASYPILOT:<IP>` als Broadcast auf Port 4242 aus. Die App
hört mit und verbindet sich selbst. Blockiert das Netz Broadcasts (AP-Isolation), kann man die IP
im Dashboard eingeben.

## Warum WebSocket statt HTTP?

Telemetrie kommt zehnmal pro Sekunde, Befehle kommen jederzeit. Eine offene WebSocket-Verbindung
spart den Verbindungsaufbau pro Nachricht. Sie merkt außerdem sofort, wenn das Handy weg ist:
Dann stoppt die Firmware in SOUND und RC die Motoren.

## Warum MSP?

Betaflight spricht MSP (MultiWii Serial Protocol) auf jedem UART. Es gibt fertige Nachrichten für
Lage (`MSP_ATTITUDE`), Akku (`MSP_ANALOG`) und Motoren (`MSP_SET_MOTOR`). Am Flight Controller
muss dafür nichts umgebaut werden.

## Das Relay

`relay_server.py` nimmt Telemetrie per WebSocket auf Port 8080 an und verteilt sie als
UDP-Broadcast im LAN. Mit `start_system.sh` wird es über einen Ngrok-Tunnel von außen erreichbar.
So kann ein ESP32 in einem anderen Netz seine Daten zur App schicken. Weil Broadcasts nur im
eigenen Netz ankommen, läuft das Relay auf einem Laptop und nicht in der Cloud.

Formate im Detail: [WebSocket-Befehle](../../reference/websocket-befehle),
[Telemetrie](../../reference/telemetrie), [MSP](../../reference/msp).
