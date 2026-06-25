import asyncio
import websockets
import socket
import json
import logging
import os

# Logging — configurable via LOG_LEVEL (default INFO). Replaces bare print() calls
# so the relay can be run as a service with structured, level-filtered output.
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
)
log = logging.getLogger("easypilot.relay")

# UDP Setup (Local Broadcast for the iOS App)
UDP_IP = "255.255.255.255"
UDP_PORT = 4242
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

async def handle_esp_connection(websocket):
    log.info("ESP32 connected from %s", websocket.remote_address)
    try:
        async for message in websocket:
            # Per-message logging is noisy — keep it at DEBUG level.
            log.debug("Received from ESP32: %s", message)

            # Forward the exact same JSON string via UDP Broadcast
            encoded_msg = message.encode('utf-8')
            sock.sendto(encoded_msg, (UDP_IP, UDP_PORT))

            # Also send to localhost in case the iOS Simulator runs on this Mac
            sock.sendto(encoded_msg, ("127.0.0.1", UDP_PORT))

    except websockets.exceptions.ConnectionClosed:
        log.info("ESP32 disconnected")
    except Exception:
        log.exception("Error while relaying ESP32 message")

async def main():
    log.info("EasyPilot Relay Server (WebSocket -> UDP) starting")
    log.info("Listening for ESP32 on ws://localhost:8080")
    log.info("Broadcasting to iOS app on UDP %s:%d", UDP_IP, UDP_PORT)

    # Start the WebSocket server on port 8080
    async with websockets.serve(handle_esp_connection, "0.0.0.0", 8080):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
