import asyncio
import websockets

async def test_connect():
    uri = "wss://primate-finer-frankly.ngrok-free.app/"
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
