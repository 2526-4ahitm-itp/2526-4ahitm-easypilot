#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUDP.h>
#include <WebSocketsServer.h>

#include "secrets_auto.h"

const char* ssid     = SECRETS_WIFI_SSID;
const char* password = SECRETS_WIFI_PASS;

const int WS_PORT    = 81;    // WebSocket server – telemetry out, commands in
const int BEACON_PORT = 4242; // UDP beacon – iOS uses this to discover the ESP32 IP

const unsigned long TELEMETRY_INTERVAL_MS = 100;   // 10 Hz
const unsigned long BEACON_INTERVAL_MS    = 5000;  // every 5 s

WebSocketsServer wsServer(WS_PORT);
WiFiUDP beaconUDP;

// ----- Simulated telemetry state -----
float roll      = 0.0;
float pitch     = 0.0;
float yaw       = 0.0;
float increment = 0.5;

int   m1 = 1000, m2 = 1000, m3 = 1000, m4 = 1000;
float voltage           = 16.8;
int   batteryPercentage = 100;

unsigned long lastTelemetryTime = 0;
unsigned long lastBeaconTime    = 0;
unsigned long safeTestEndTime   = 0;

// ----- Command handler (called from WS event) -----
void handleCommand(const String& cmd) {
  if (cmd == "SAFE_TEST") {
    safeTestEndTime = millis() + 500;
    m1 = 1050;
    Serial.println("[CMD] Safe Test: M1=1050 PWM for 500 ms");
  } else {
    Serial.printf("[CMD] Unknown command: %s\n", cmd.c_str());
  }
}

// ----- WebSocket event handler -----
void onWsEvent(uint8_t num, WStype_t type, uint8_t* payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED:
      Serial.printf("[WS] Client #%u connected from %s\n",
                    num, wsServer.remoteIP(num).toString().c_str());
      break;
    case WStype_DISCONNECTED:
      Serial.printf("[WS] Client #%u disconnected\n", num);
      break;
    case WStype_TEXT: {
      String cmd = String((char*)payload);
      cmd.trim();
      handleCommand(cmd);
      break;
    }
    default:
      break;
  }
}

// ----- Setup -----
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- ESP32 Booting Up ---");

  WiFi.setSleep(false);
  WiFi.mode(WIFI_STA);

  // Scan for networks to see what's available
  Serial.println("Scanning for nearby WiFi networks...");
  int n = WiFi.scanNetworks();
  if (n == 0) {
    Serial.println("No networks found.");
  } else {
    Serial.printf("%d networks found:\n", n);
    for (int i = 0; i < n; ++i) {
      Serial.printf("%d: %s (RSSI: %d, Ch: %d, Auth: %d)\n",
                    i + 1, WiFi.SSID(i).c_str(), WiFi.RSSI(i),
                    WiFi.channel(i), WiFi.encryptionType(i));
      delay(10);
    }
  }

  WiFi.begin(ssid, password);
  Serial.printf("\nConnecting to WiFi: %s\n", ssid);

  int counter = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    if (counter % 10 == 0 && counter > 0) {
      Serial.printf(" [Status: %d, RSSI: %d]\n", WiFi.status(), WiFi.RSSI());
    }
    if (++counter > 60) {
      Serial.println("\nWiFi timeout – rebooting...");
      ESP.restart();
    }
  }

  Serial.println("\nWiFi connected!");
  Serial.print("SSID:         "); Serial.println(WiFi.SSID());
  Serial.print("BSSID:        "); Serial.println(WiFi.BSSIDstr());
  Serial.print("RSSI:         "); Serial.print(WiFi.RSSI()); Serial.println(" dBm");
  Serial.print("Local IP:     "); Serial.println(WiFi.localIP());
  Serial.print("Subnet Mask:  "); Serial.println(WiFi.subnetMask());
  Serial.print("Gateway IP:   "); Serial.println(WiFi.gatewayIP());
  Serial.print("Broadcast IP: "); Serial.println(WiFi.broadcastIP());

  wsServer.begin();
  wsServer.onEvent(onWsEvent);
  Serial.printf("WebSocket server on port %d\n", WS_PORT);

  beaconUDP.begin(BEACON_PORT);
  Serial.printf("UDP beacon on port %d every %lu s\n",
                BEACON_PORT, BEACON_INTERVAL_MS / 1000);
}

// ----- Loop -----
void loop() {
  wsServer.loop();

  unsigned long now = millis();

  // End safe-test pulse when timer expires
  if (safeTestEndTime > 0 && now > safeTestEndTime) {
    m1 = 1000;
    safeTestEndTime = 0;
    Serial.println("[CMD] Safe Test ended: M1 reset");
  }

  // Push telemetry to all WebSocket clients (10 Hz)
  if (now - lastTelemetryTime > TELEMETRY_INTERVAL_MS) {
    String json = "{\"roll\": "               + String(roll, 2)
                + ", \"pitch\": "             + String(pitch, 2)
                + ", \"yaw\": "               + String(yaw, 2)
                + ", \"m1\": "                + String(m1)
                + ", \"m2\": "                + String(m2)
                + ", \"m3\": "                + String(m3)
                + ", \"m4\": "                + String(m4)
                + ", \"voltage\": "           + String(voltage, 2)
                + ", \"batteryPercentage\": " + String(batteryPercentage) + "}";

    wsServer.broadcastTXT(json);
    lastTelemetryTime = now;

    // Advance simulated values
    roll  += increment;
    pitch += increment * 0.5;
    yaw   += increment * 0.2;
    if (abs(roll) > 90.0) increment = -increment;

    if (safeTestEndTime == 0) m1 = random(1100, 1800);
    m2 = random(1100, 1800);
    m3 = random(1100, 1800);
    m4 = random(1100, 1800);

    voltage -= 0.005;
    if (voltage < 13.0) voltage = 16.8;
    batteryPercentage = (int)((voltage - 13.0) / (16.8 - 13.0) * 100);
    batteryPercentage = constrain(batteryPercentage, 0, 100);
  }

  // Broadcast UDP beacon so iOS can discover this device's IP (every 5 s)
  if (now - lastBeaconTime > BEACON_INTERVAL_MS) {
    String beacon = "EASYPILOT:" + WiFi.localIP().toString();
    beaconUDP.beginPacket(WiFi.broadcastIP(), BEACON_PORT);
    beaconUDP.print(beacon);
    beaconUDP.endPacket();
    Serial.printf("[Beacon] %s\n", beacon.c_str());
    lastBeaconTime = now;
  }
}
