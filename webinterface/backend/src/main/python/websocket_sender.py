import asyncio
import websockets
import json
import serial
import struct
import time

# ==============================================================================
# 1. KONFIGURATION
# ==============================================================================
SERIAL_PORT = 'COM3'       # Bitte anpassen!
BAUD_RATE = 115200

# PID Parameter (Horizontal-Stabilisierung)
# Ziel: Die Drohne soll immer auf 0 Grad (eben) zurückkehren.
KP = 1.5   
KI = 0.0   
KD = 0.8   

# Motor Einstellungen
# VORSICHT: 1050 ist oft Leerlauf ("Air Mode"). Zum Abheben muss dieser Wert höher sein.
# Teste erst mit 1000 oder 1050 (am Boden/ohne Props), dann langsam steigern.
BASE_THROTTLE = 1050       
MAX_THROTTLE  = 1800       

# MSP IDs
MSP_ATTITUDE  = 108
MSP_SET_MOTOR = 214

# Status-Variable zum Beenden der Loops
is_running = True
drone_state = {"roll": 0.0, "pitch": 0.0}

# ==============================================================================
# 2. SERIAL VERBINDUNG
# ==============================================================================
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.02)
    print(f"[INIT] Verbunden mit {SERIAL_PORT}")
except Exception as e:
    print(f"[ERROR] Serial Port Fehler: {e}")
    ser = None

# ==============================================================================
# 3. PID CONTROLLER KLASSE
# ==============================================================================
class PIDController:
    def __init__(self, kp, ki, kd):
        self.kp = kp; self.ki = ki; self.kd = kd
        self.integral = 0.0
        self.last_error = 0.0
        self.last_time = time.perf_counter()

    def update(self, setpoint, measurement):
        now = time.perf_counter()
        dt = now - self.last_time
        if dt <= 0: dt = 0.001

        error = setpoint - measurement
        
        # Integral
        self.integral += error * dt
        self.integral = max(-50, min(50, self.integral)) # Begrenzung

        # Derivative
        derivative = (error - self.last_error) / dt

        # Output
        output = (self.kp * error) + (self.ki * self.integral) + (self.kd * derivative)

        self.last_error = error
        self.last_time = now
        return output

# Regler initialisieren
pid_roll = PIDController(KP, KI, KD)
pid_pitch = PIDController(KP, KI, KD)

# ==============================================================================
# 4. MSP FUNKTIONEN
# ==============================================================================
def send_msp(cmd, payload):
    if ser is None: return
    size = len(payload)
    crc = size ^ cmd
    for b in payload: crc ^= b
    data = b'$M<' + struct.pack('<BB', size, cmd) + payload + struct.pack('<B', crc)
    ser.write(data)

def read_attitude():
    """ Liest Roll/Pitch von der Drohne """
    if ser is None: return
    send_msp(MSP_ATTITUDE, b'')
    try:
        if ser.in_waiting > 10:
            if ser.read(1) == b'$' and ser.read(1) == b'M' and ser.read(1) == b'>':
                size = ord(ser.read(1))
                cmd = ord(ser.read(1))
                if cmd == MSP_ATTITUDE and size >= 6:
                    data = ser.read(6)
                    ser.read(1) # CRC
                    r, p, y = struct.unpack('<hhh', data)
                    drone_state["roll"] = r / 10.0
                    drone_state["pitch"] = p / 10.0
            else:
                ser.reset_input_buffer()
    except:
        pass

def write_motors(m1, m2, m3, m4):
    """ Sendet Motorwerte 1000-2000 """
    # Limitierung
    m1 = int(max(1000, min(MAX_THROTTLE, m1)))
    m2 = int(max(1000, min(MAX_THROTTLE, m2)))
    m3 = int(max(1000, min(MAX_THROTTLE, m3)))
    m4 = int(max(1000, min(MAX_THROTTLE, m4)))
    
    payload = struct.pack('<HHHHHHHH', m1, m2, m3, m4, 1000, 1000, 1000, 1000)
    send_msp(MSP_SET_MOTOR, payload)

# ==============================================================================
# 5. STABILISIERUNGS LOOP
# ==============================================================================
async def task_stabilization(websocket):
    print("[START] Stabilisierung aktiv. Druecke STRG+C zum Stoppen.")
    
    while is_running:
        # A. Daten holen
        read_attitude()
        
        # B. PID Berechnen (Sollwert ist 0.0 Grad)
        corr_roll = pid_roll.update(0.0, drone_state["roll"])
        corr_pitch = pid_pitch.update(0.0, drone_state["pitch"])

        # C. Mixer (Quad X Konfiguration)
        # Basis Gas
        thr = BASE_THROTTLE
        
        # Mischer Logik (Betaflight Standard)
        # M1 (HR), M2 (VR), M3 (HL), M4 (VL)
        # Vorzeichen ggf. anpassen, wenn Drohne falsch reagiert!
        m1 = thr - corr_roll + corr_pitch 
        m2 = thr - corr_roll - corr_pitch 
        m3 = thr + corr_roll + corr_pitch 
        m4 = thr + corr_roll - corr_pitch 

        # D. Motoren ansteuern
        write_motors(m1, m2, m3, m4)

        # E. Telemetrie an Browser senden (optional, nur zur Info)
        if websocket:
            try:
                await websocket.send(json.dumps({
                    "roll": round(drone_state["roll"], 2),
                    "pitch": round(drone_state["pitch"], 2),
                    "m1": int(m1)
                }))
            except:
                pass

        # F. Loop Frequenz (ca. 100Hz)
        await asyncio.sleep(0.01)

# ==============================================================================
# 6. SERVER HANDLER
# ==============================================================================
async def main_handler(websocket):
    global is_running
    is_running = True
    print("[CLIENT] Browser verbunden.")

    try:
        # Führe die Stabilisierung aus, bis die Verbindung bricht
        await task_stabilization(websocket)
    except websockets.exceptions.ConnectionClosed:
        print("[CLIENT] Verbindung getrennt.")
    finally:
        # Wenn der Loop endet (warum auch immer), Motoren AUS!
        is_running = False
        print("[STOP] Motoren werden abgeschaltet.")
        # Mehrfach senden zur Sicherheit
        for _ in range(5):
            write_motors(1000, 1000, 1000, 1000)
            time.sleep(0.01)

async def main():
    print("Server läuft auf ws://localhost:8765")
    async with websockets.serve(main_handler, "localhost", 8765):
        await asyncio.Future() # Hält den Server am Leben

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[ABBRUCH] Manuell beendet.")
        if ser:
            # Not-Aus Panic Write ohne Async
            payload = struct.pack('<HHHHHHHH', 1000,1000,1000,1000, 1000,1000,1000,1000)
            header = b'$M<' + struct.pack('<BB', 16, MSP_SET_MOTOR) + payload
            checksum = 16 ^ MSP_SET_MOTOR
            for b in payload: checksum ^= b
            ser.write(header + struct.pack('<B', checksum))
            ser.close()