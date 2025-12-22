import asyncio
import websockets
import json
import serial
import struct
import math

SERIAL_PORT = 'COM3'
BAUD_RATE = 115200
MSP_ATTITUDE = 108

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    print(f" Serial Port {SERIAL_PORT} erfolgreich geöffnet.")
except Exception as e:
    print(f"FEHLER: Konnte {SERIAL_PORT} nicht öffnen.")
    print(f"Exception: {e}")
    ser = None

def send_msp_request(command):
    if ser is None: return
    header = b'$M<'
    size = 0
    crc = 0 ^ command
    data = struct.pack('<BBB', size, command, crc)
    ser.write(header + data)

def read_msp_response():
    if ser is None: return None
    while ser.in_waiting > 0:
        if ser.read() == b'$':
            if ser.read() == b'M':
                if ser.read() == b'>':
                    try:
                        size = struct.unpack('<B', ser.read())[0]
                        cmd = struct.unpack('<B', ser.read())[0]
                        data = ser.read(size)
                        ser.read()
                        return data
                    except:
                        pass
    return None

async def telemetry_server(websocket):


    if ser is None:
        await websocket.send(json.dumps({"error": "Keine Drohne verbunden"}))
        return

    try:
        while True:

            send_msp_request(MSP_ATTITUDE)


            await asyncio.sleep(0.01)


            data = read_msp_response()

            if data and len(data) >= 6:
                roll_dec, pitch_dec, yaw_dec = struct.unpack('<hhh', data[:6])


                telemetry = {
                    "roll": math.radians(roll_dec / 10.0),
                    "pitch": -math.radians(pitch_dec / 10.0),
                    "yaw": -math.radians(yaw_dec / 10.0)
                }

                await websocket.send(json.dumps(telemetry))


            await asyncio.sleep(0.016)

    except websockets.exceptions.ConnectionClosed:
        print("🔌 Ein Client hat die Verbindung getrennt.")
    except Exception as e:
        print(f"⚠️ Fehler im Loop: {e}")

async def main():
    if ser is None:
        return

    print(f"Starte WebSocket Server auf ws://localhost:8765")
    async with websockets.serve(telemetry_server, "localhost", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        if ser: ser.close()
        print("Beendet.")