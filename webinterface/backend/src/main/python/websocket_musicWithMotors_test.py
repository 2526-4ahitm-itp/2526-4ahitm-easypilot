import asyncio
import websockets
import json
import serial
import struct

# ------------------------------------------------------------------
# KONFIGURATION
# ------------------------------------------------------------------
SERIAL_PORT = 'COM3'       #  Anpassen je nach System (z.B. in linux /dev/tty** man muss im /dev Verzeichnis nachsehen welcher Port genutzt wird)
BAUD_RATE = 115200
MSP_SET_MOTOR = 214

# Geschwindigkeit der Melodie
# 0.0055 Sekunden pro Zeiteinheit (ca. 5.5ms)
TIME_MULTIPLIER = 0.0055

# ------------------------------------------------------------------
# MELODIE DATEN (Tetris)
# ------------------------------------------------------------------
tetris_melody = [
    # Takt 1
    {"m1": 30, "m2": 0,  "m3": 0,  "m4": 80, "time": 30},
    {"m1": 0,  "m2": 50, "m3": 50, "m4": 75, "time": 15},
    {"m1": 30, "m2": 0,  "m3": 0,  "m4": 77, "time": 15},
    {"m1": 0,  "m2": 50, "m3": 50, "m4": 80, "time": 30},
    {"m1": 25, "m2": 0,  "m3": 0,  "m4": 77, "time": 15},
    {"m1": 0,  "m2": 45, "m3": 45, "m4": 75, "time": 15},

    # Takt 2
    {"m1": 25, "m2": 0,  "m3": 0,  "m4": 70, "time": 30},
    {"m1": 0,  "m2": 45, "m3": 45, "m4": 0,  "time": 15},
    {"m1": 25, "m2": 0,  "m3": 0,  "m4": 70, "time": 15},
    {"m1": 0,  "m2": 45, "m3": 45, "m4": 77, "time": 30},
    {"m1": 30, "m2": 0,  "m3": 0,  "m4": 80, "time": 30},
    {"m1": 0,  "m2": 50, "m3": 50, "m4": 75, "time": 15},
    {"m1": 30, "m2": 0,  "m3": 0,  "m4": 77, "time": 15},

    # Ausklang / Ende
    {"m1": 30, "m2": 50, "m3": 60, "m4": 80, "time": 60},
    {"m1": 0,  "m2": 0,  "m3": 0,  "m4": 0,  "time": 20}
]

# ------------------------------------------------------------------
# SERIAL INITIALISIERUNG
# ------------------------------------------------------------------
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    print(f"[INFO] Serial Port {SERIAL_PORT} erfolgreich geoeffnet.")
except Exception as e:
    print(f"[ERROR] Konnte {SERIAL_PORT} nicht oeffnen.")
    print(f"[DEBUG] {e}")
    ser = None

# ------------------------------------------------------------------
# MSP PROTOKOLL FUNKTIONEN
# ------------------------------------------------------------------
def send_msp_command(command, payload):
    """ Erstellt und sendet ein MSP v1 Paket """
    if ser is None:
        return

    header = b'$M<'
    size = len(payload)

    # XOR Checksumme berechnen
    crc = size ^ command
    for byte in payload:
        crc ^= byte

    msg = header + struct.pack('<BB', size, command) + payload + struct.pack('<B', crc)
    ser.write(msg)

def map_percent_to_msp(percent):
    """ Konvertiert 0-100% in 1000-2000 (µs) """
    percent = max(0, min(100, percent))
    return int(1000 + (percent * 10))

# ------------------------------------------------------------------
# HAUPTLOGIK
# ------------------------------------------------------------------
async def play_melody_once(websocket=None):
    """ Spielt die Melodie exakt einmal ab """
    if ser is None:
        if websocket:
            await websocket.send(json.dumps({"error": "Kein Serial Port"}))
        return

    print(f"[INFO] Starte Melodie ({len(tetris_melody)} Schritte)...")

    for i, step in enumerate(tetris_melody):
        # 1. Prozentwerte in MSP-Werte (1000-2000) umrechnen
        val_m1 = map_percent_to_msp(step.get("m1", 0))
        val_m2 = map_percent_to_msp(step.get("m2", 0))
        val_m3 = map_percent_to_msp(step.get("m3", 0))
        val_m4 = map_percent_to_msp(step.get("m4", 0))

        # 2. Payload erstellen (8 Motoren unsigned short)
        payload = struct.pack('<HHHHHHHH',
                              val_m1, val_m2, val_m3, val_m4,
                              1000, 1000, 1000, 1000)

        # 3. An Drohne senden
        send_msp_command(MSP_SET_MOTOR, payload)

        # 4. Optional: Feedback an HTML-Client
        if websocket:
            try:
                status_msg = {
                    "step": i + 1,
                    "m1": step.get("m1", 0),
                    "m2": step.get("m2", 0),
                    "m3": step.get("m3", 0),
                    "m4": step.get("m4", 0)
                }
                await websocket.send(json.dumps(status_msg))
            except:
                pass

        # 5. Warten
        duration = step.get("time", 10)
        await asyncio.sleep(duration * TIME_MULTIPLIER)

    # Ende der Sequenz: Motoren stoppen
    print("[INFO] Melodie beendet. Stoppe Motoren.")
    stop_motors()

    # Finales Feedback an UI
    if websocket:
        await websocket.send(json.dumps({"m1":0, "m2":0, "m3":0, "m4":0}))

def stop_motors():
    """ Sendet den Befehl zum Ausschalten aller Motoren """
    if ser is None: return
    stop_payload = struct.pack('<HHHHHHHH', 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000)
    # Sicherheitsredundanz: Mehrfach senden
    for _ in range(3):
        send_msp_command(MSP_SET_MOTOR, stop_payload)

async def server_handler(websocket):
    print("[INFO] Client verbunden.")
    try:
        # Einmaliges Abspielen
        await play_melody_once(websocket)

        # Verbindung offen halten, aber nichts mehr tun
        print("[INFO] Warte im Leerlauf...")
        await asyncio.Future()

    except websockets.exceptions.ConnectionClosed:
        print("[INFO] Client getrennt.")
    except Exception as e:
        print(f"[ERROR] Fehler im Handler: {e}")
    finally:
        stop_motors()

async def main():
    if ser is None:
        print("[WARNUNG] Server laeuft im Simulationsmodus (kein Serial).")

    print("[INFO] Starte WebSocket Server auf ws://localhost:8765")
    async with websockets.serve(server_handler, "localhost", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Programm vom Benutzer beendet.")
        stop_motors()
        if ser:
            ser.close()