import asyncio
import websockets
import socket
import json

# UDP Setup (Local Broadcast for the iOS App)
UDP_IP = "255.255.255.255"
UDP_PORT = 4242
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

async def handle_esp_connection(websocket):
    print(f"[+] ESP32 Connected from {websocket.remote_address}")
    try:
        async for message in websocket:
            # Print the received message (optional, can be noisy)
            print(f"Received from ESP32: {message}")
            
            # Forward the exact same JSON string via UDP Broadcast
            encoded_msg = message.encode('utf-8')
            sock.sendto(encoded_msg, (UDP_IP, UDP_PORT))
            
            # Also send to localhost just in case you are testing in the iOS Simulator on this Mac
            sock.sendto(encoded_msg, ("127.0.0.1", UDP_PORT))
            
    except websockets.exceptions.ConnectionClosed:
        print("[-] ESP32 Disconnected")
    except Exception as e:
        print(f"[!] Error: {e}")

async def main():
    print("=====================================================")
    print("  EasyPilot Relay Server (WebSocket -> UDP) Started")
    print("  Listening for ESP32 on ws://localhost:8080")
    print("  Broadcasting to iOS App on UDP 255.255.255.255:4242")
    print("=====================================================")
    
    # Start the WebSocket server on port 8080
    async with websockets.serve(handle_esp_connection, "0.0.0.0", 8080):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
