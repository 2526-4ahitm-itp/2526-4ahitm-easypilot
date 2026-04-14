#!/bin/bash

# Beende alte Instanzen, falls sie noch laufen
killall ngrok 2>/dev/null
pkill -f relay_server.py 2>/dev/null

echo "=========================================================="
echo "  EasyPilot System Starter"
echo "=========================================================="

# 1. Ngrok im Hintergrund starten
echo "[1/3] Starte Ngrok Tunnel auf Port 8080..."
ngrok http 8080 > /dev/null &

# Warten, bis Ngrok bereit ist
sleep 4

# 2. Die öffentliche URL von der Ngrok API abrufen
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o 'https://[^"]*ngrok-free.app' | head -n 1)

if [ -z "$NGROK_URL" ]; then
    echo "FEHLER: Konnte keine Ngrok-URL finden."
    echo "Stelle sicher, dass Ngrok installiert ist und dein Authtoken gesetzt wurde."
    exit 1
fi

CLEAN_URL=$(echo $NGROK_URL | sed 's/https:\/\///')

echo "----------------------------------------------------------"
echo "  DEINE NGROK URL: $NGROK_URL"
echo "  FÜR ESP32 (main.cpp): $CLEAN_URL"
echo "----------------------------------------------------------"
echo "[2/3] Ngrok ist bereit."

# 3. Python Relay Server starten
echo "[3/3] Starte Python Relay Server..."
echo "      (Drücke Strg+C zum Beenden des gesamten Systems)"
echo "----------------------------------------------------------"

python3 webinterface/backend/src/main/python/relay_server.py
