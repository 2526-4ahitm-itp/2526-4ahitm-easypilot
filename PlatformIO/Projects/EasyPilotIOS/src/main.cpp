#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>

// WiFi Configuration via Build Flags
// If SECRETS_WIFI_SSID is not defined in platformio.ini, fallback to defaults
#ifndef SECRETS_WIFI_SSID
#define SECRETS_WIFI_SSID "Sim"
#endif

#ifndef SECRETS_WIFI_PASS
#define SECRETS_WIFI_PASS "123456789"
#endif

const char* ssid = SECRETS_WIFI_SSID;
const char* password = SECRETS_WIFI_PASS;

// UDP Configuration
WiFiUDP udp;
const int udpPort = 4242;
IPAddress remoteUdpIP; // Stores the IP address of the iPhone
bool clientConnected = false;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- ESP32 Booting Up ---");

  Serial.printf("Connecting to WiFi: %s\n", ssid);
  WiFi.begin(ssid, password);

  // Wait for connection
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  // Start UDP
  if (udp.begin(udpPort)) {
    Serial.printf("UDP server listening on port %d\n", udpPort);
    Serial.println("Waiting for a message from the iOS app to establish connection...");
  } else {
    Serial.println("Failed to start UDP server!");
  }
  Serial.println("------------------------");
}

// Simulation Data
float roll = 0.0;
float pitch = 0.0;
float yaw = 0.0;
float increment = 0.5;

void loop() {
  // First, check for an incoming packet to identify the client (iPhone)
  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    if (!clientConnected) {
      remoteUdpIP = udp.remoteIP();
      clientConnected = true;
      Serial.print("iOS app connected from IP: ");
      Serial.println(remoteUdpIP);
    }
    // You can read the packet data if needed, but for now we just need the IP
    // char packetBuffer[255];
    // udp.read(packetBuffer, 255);
  }

  // If we have a client's IP, start sending data
  if (clientConnected) {
    // Create JSON payload
    String jsonPayload = "{\"roll\": " + String(roll) +
                         ", \"pitch\": " + String(pitch) +
                         ", \"yaw\": " + String(yaw) + "}";

    // Send UDP packet directly to the iPhone
    udp.beginPacket(remoteUdpIP, udpPort);
    udp.print(jsonPayload);
    udp.endPacket();

    Serial.println("Sent: " + jsonPayload);

    // Simulate changing gyro data
    roll += increment;
    pitch += increment * 0.5;
    yaw += increment * 0.2;
    if (abs(roll) > 90.0) increment = -increment;
  }

  delay(100); // Loop every 100ms
}
