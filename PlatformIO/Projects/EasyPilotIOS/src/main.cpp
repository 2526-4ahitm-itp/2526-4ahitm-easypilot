#include <Arduino.h>
#include <WiFi.h>
#include <WebSocketsClient.h>

// Include the auto-generated secrets (created by load_secrets.py)
#include "secrets_auto.h"

const char* ssid = SECRETS_WIFI_SSID;
const char* password = SECRETS_WIFI_PASS;
const char* ngrokHost = SECRETS_NGROK_HOST; 
const int ngrokPort = SECRETS_NGROK_PORT;

WebSocketsClient webSocket;
bool isConnected = false;

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.println("[WS] Disconnected!");
      isConnected = false;
      break;
    case WStype_CONNECTED:
      Serial.printf("[WS] Connected to Server on port %d!\n", ngrokPort);
      isConnected = true;
      break;
    case WStype_TEXT:
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
  Serial.println("\n--- ESP32 Booting Up (TCP Tunnel Mode) ---");

  WiFi.setSleep(false); // Stabilisiert die WLAN-Verbindung

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

  String hostStr = String(ngrokHost);
  hostStr.replace("tcp://", ""); // Nur für den Fall, dass es in der secrets.ini steht
  
  Serial.print("Connecting via raw TCP to WebSocket at: ");
  Serial.print(hostStr);
  Serial.print(":");
  Serial.println(ngrokPort);
  
  // WICHTIG: Komplett unverschlüsselt (begin statt beginSSL) auf den dynamischen TCP-Port
  webSocket.begin(hostStr.c_str(), ngrokPort, "/");
  
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
  
  Serial.println("WebSocket Client started...");
}

float roll = 0.0;
float pitch = 0.0;
float yaw = 0.0;
float increment = 0.5;

int m1 = 1000;
int m2 = 1000;
int m3 = 1000;
int m4 = 1000;
float voltage = 16.8; 
int batteryPercentage = 100;

unsigned long lastSendTime = 0;

void loop() {
  webSocket.loop();

  if (isConnected && millis() - lastSendTime > 100) {
    
    String jsonPayload = "{\"roll\": " + String(roll) +
                         ", \"pitch\": " + String(pitch) +
                         ", \"yaw\": " + String(yaw) + 
                         ", \"m1\": " + String(m1) +
                         ", \"m2\": " + String(m2) +
                         ", \"m3\": " + String(m3) +
                         ", \"m4\": " + String(m4) +
                         ", \"voltage\": " + String(voltage, 2) +
                         ", \"batteryPercentage\": " + String(batteryPercentage) + "}";

    webSocket.sendTXT(jsonPayload);
    lastSendTime = millis();

    roll += increment;
    pitch += increment * 0.5;
    yaw += increment * 0.2;
    if (abs(roll) > 90.0) increment = -increment;
    
    m1 = random(1100, 1800);
    m2 = random(1100, 1800);
    m3 = random(1100, 1800);
    m4 = random(1100, 1800);
    
    voltage -= 0.005;
    if (voltage < 13.0) voltage = 16.8; 
    
    batteryPercentage = (int)((voltage - 13.0) / (16.8 - 13.0) * 100);
    if (batteryPercentage < 0) batteryPercentage = 0;
    if (batteryPercentage > 100) batteryPercentage = 100;
  }
}
