import asyncio
import os
import websockets

# Set RELAY_WS_URL to your relay/ngrok endpoint, e.g.
#   export RELAY_WS_URL="wss://<your-subdomain>.ngrok-free.app/"
async def test_connect():
    uri = os.environ.get("RELAY_WS_URL", "wss://YOUR-NGROK-SUBDOMAIN.ngrok-free.app/")
    headers = {"ngrok-skip-browser-warning": "true"}
    print(f"Connecting to {uri}")
    try:
        async with websockets.connect(uri, additional_headers=headers) as websocket:
            print("Connected successfully via Python!")
            await websocket.send('{"test": "hello"}')
            print("Message sent.")
    except Exception as e:
        print(f"Connection failed: {e}")

asyncio.run(test_connect())
