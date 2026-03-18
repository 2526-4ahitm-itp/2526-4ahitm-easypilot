#include <Arduino.h>
#include <WiFi.h>
#include <WebSocketsClient.h>

// Include the auto-generated secrets (created by load_secrets.py)
#include "secrets_auto.h"

const char* ssid = SECRETS_WIFI_SSID;
const char* password = SECRETS_WIFI_PASS;

// ==========================================
// NGROK KONFIGURATION
// ==========================================
const char* ngrokHost = SECRETS_NGROK_HOST; 
const int ngrokPort = 443; // 443 für HTTPS/WSS (sichere Verbindung)

WebSocketsClient webSocket;
bool isConnected = false;

// Event-Handler für WebSocket-Ereignisse
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.println("[WS] Disconnected!");
      isConnected = false;
      break;
    case WStype_CONNECTED:
      Serial.printf("[WS] Connected to url: %s\n", payload);
      isConnected = true;
      break;
    case WStype_TEXT:
      Serial.printf("[WS] Message from Server: %s\n", payload);
      break;
    case WStype_BIN:
    case WStype_ERROR:      
    case WStype_FRAGMENT_TEXT_START:
    case WStype_FRAGMENT_BIN_START:
    case WStype_FRAGMENT:
    case WStype_FRAGMENT_FIN:
      break;
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- ESP32 Booting Up (WebSocket Mode) ---");

  Serial.printf("Connecting to WiFi: %s\n", ssid);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int counter = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    counter++;
    
    if (counter > 60) {
      Serial.println("\nConnection timeout! Rebooting...");
      ESP.restart();
    }
  }
  Serial.println("\nWiFi connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  // WebSocket starten
  // wss:// (secure) Verbindung zu Ngrok auf Port 443
  webSocket.setExtraHeaders("ngrok-skip-browser-warning: true\r\n");
  
  // WICHTIG: Das "" (leere String) am Ende deaktiviert die Zertifikatsprüfung,
  // wodurch der ESP32 nicht mehr den ngrok-EOF Fehler wirft.
  webSocket.beginSSL(ngrokHost, ngrokPort, "/", "", "");
  
  webSocket.onEvent(webSocketEvent);

  // Automatischer Reconnect alle 5 Sekunden, falls die Verbindung abbricht
  webSocket.setReconnectInterval(5000);
  
  Serial.println("WebSocket Client started, waiting for connection...");
}

// Simulation Data
float roll = 0.0;
float pitch = 0.0;
float yaw = 0.0;
float increment = 0.5;

int m1 = 1000;
int m2 = 1000;
int m3 = 1000;
int m4 = 1000;
float voltage = 16.8; // 4S fully charged
int batteryPercentage = 100;

unsigned long lastSendTime = 0;

void loop() {
  // WebSocket am Leben erhalten
  webSocket.loop();

  // Alle 100ms Daten senden, WENN verbunden
  if (isConnected && millis() - lastSendTime > 100) {
    
    // Create JSON payload
    String jsonPayload = "{\"roll\": " + String(roll) +
                         ", \"pitch\": " + String(pitch) +
                         ", \"yaw\": " + String(yaw) + 
                         ", \"m1\": " + String(m1) +
                         ", \"m2\": " + String(m2) +
                         ", \"m3\": " + String(m3) +
                         ", \"m4\": " + String(m4) +
                         ", \"voltage\": " + String(voltage, 2) +
                         ", \"batteryPercentage\": " + String(batteryPercentage) + "}";

    // Sende die Daten an den Ngrok-Server (der sie dann an den Python-Relay leitet)
    webSocket.sendTXT(jsonPayload);
    // Serial.println("Sent: " + jsonPayload); // Optional: Kommentar entfernen für Debugging

    lastSendTime = millis();

    // Simulate changing gyro data
    roll += increment;
    pitch += increment * 0.5;
    yaw += increment * 0.2;
    if (abs(roll) > 90.0) increment = -increment;
    
    // Simulate fluctuating motors (1000 to 2000 PWM)
    m1 = random(1100, 1800);
    m2 = random(1100, 1800);
    m3 = random(1100, 1800);
    m4 = random(1100, 1800);
    
    // Simulate battery drain slowly
    voltage -= 0.005;
    if (voltage < 13.0) voltage = 16.8; 
    
    // Calculate percentage based on 13.0V (0%) and 16.8V (100%)
    batteryPercentage = (int)((voltage - 13.0) / (16.8 - 13.0) * 100);
    if (batteryPercentage < 0) batteryPercentage = 0;
    if (batteryPercentage > 100) batteryPercentage = 100;
  }
}
