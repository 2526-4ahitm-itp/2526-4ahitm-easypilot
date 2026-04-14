import socket
import time
import json
import random

# Konfiguration
UDP_IP = "255.255.255.255" # Broadcast Adresse
UDP_PORT = 5000
DELAY = 0.05 # 20Hz (50ms)

print(f"Starte Dummy-Sender auf {UDP_IP}:{UDP_PORT}")
print("Druecke STRG+C zum Beenden")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

try:
    while True:
        # Zufallswerte generieren (ähnlich wie im ESP32 Code)
        # Roll/Pitch/Yaw in Radians (-1.0 bis 1.0 entspricht ca. -57 bis +57 Grad)
        roll = random.uniform(-1.0, 1.0)
        pitch = random.uniform(-1.0, 1.0)
        yaw = random.uniform(-1.0, 1.0)
        
        # Motoren (1000 - 2000)
        m1 = random.randint(1000, 2000)
        m4 = random.randint(1000, 2000)

        # JSON erstellen
        data = {
            "roll": roll,
            "pitch": pitch,
            "yaw": yaw,
            "m1": m1,
            "m4": m4
        }
        
        json_str = json.dumps(data)
        
        # Senden
        sock.sendto(json_str.encode(), (UDP_IP, UDP_PORT))
        print(f"Gesendet: {json_str}")
        
        time.sleep(DELAY)

except KeyboardInterrupt:
    print("\nBeendet.")
    sock.close()
