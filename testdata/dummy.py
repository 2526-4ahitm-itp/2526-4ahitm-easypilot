import csv
import math
import random
import time

# --- KONFIGURATION ---
FREQ = 50                # 50 Hz
DURATION_SEC = 10        # 10 Sekunden Simulation
# Sicherstellen, dass es eine ganze Zahl ist (int)
TOTAL_SAMPLES = int(FREQ * DURATION_SEC)
DT = 1.0 / FREQ          # 0.02 Sekunden pro Schritt

filename = "test_sim_data.csv"

print(f"--- STARTE SIMULATION ---")
print(f"Ziel: {TOTAL_SAMPLES} Datensätze in '{filename}'")

try:
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        
        # 1. Header schreiben
        header = ["timestamp", "roll", "pitch", "yaw", "motor1", "motor2", "motor3", "motor4"]
        writer.writerow(header)
        print("Header geschrieben.")

        # 2. Daten schreiben
        for i in range(TOTAL_SAMPLES):
            t = i * DT
            
            # Bewegung berechnen
            roll = 2.0 * math.sin(2 * math.pi * 0.5 * t) + random.gauss(0, 0.1)
            pitch = 1.5 * math.cos(2 * math.pi * 0.3 * t) + random.gauss(0, 0.1)
            yaw = 0.5 * t + random.gauss(0, 0.05)

            # Motoren berechnen
            base_throttle = 55.0
            k = 2.0
            
            m1_val = base_throttle - pitch*k + roll*k - yaw
            m2_val = base_throttle - pitch*k - roll*k + yaw
            m3_val = base_throttle + pitch*k - roll*k - yaw
            m4_val = base_throttle + pitch*k + roll*k + yaw

            # Clipping Funktion inline
            def limit(v): return max(0, min(100, v + random.gauss(0, 0.2)))

            row = [
                f"{t:.3f}",
                f"{roll:.2f}",
                f"{pitch:.2f}",
                f"{yaw:.2f}",
                f"{limit(m1_val):.2f}",
                f"{limit(m2_val):.2f}",
                f"{limit(m3_val):.2f}",
                f"{limit(m4_val):.2f}"
            ]
            
            writer.writerow(row)

            # Fortschrittsanzeige alle 100 Zeilen
            if i % 100 == 0:
                print(f"Schreibe Zeile {i}...")

    print(f"--- FERTIG! ---")
    print(f"Datei '{filename}' liegt jetzt in deinem Ordner.")

except Exception as e:
    print(f"\n!!! FEHLER AUFGETRETEN: {e} !!!")