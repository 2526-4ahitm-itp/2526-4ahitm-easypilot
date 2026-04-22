#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUDP.h>

#include "secrets_auto.h"

const char* ssid     = SECRETS_WIFI_SSID;
const char* password = SECRETS_WIFI_PASS;

// UDP: broadcast telemetry on 4242, receive commands on 4243
const int TELEMETRY_PORT = 4242;
const int COMMAND_PORT   = 4243;

WiFiUDP broadcastUDP;  // outbound – sends telemetry to all local clients
WiFiUDP commandUDP;    // inbound  – receives commands from the iOS app

// ----- Simulated telemetry state -----
float roll      = 0.0;
float pitch     = 0.0;
float yaw       = 0.0;
float increment = 0.5;

int   m1 = 1000, m2 = 1000, m3 = 1000, m4 = 1000;
float voltage           = 16.8;
int   batteryPercentage = 100;

unsigned long lastSendTime    = 0;
unsigned long safeTestEndTime = 0;  // non-zero while safe-test is active

// ----- Safe Test -----
void handleSafeTest() {
  safeTestEndTime = millis() + 500;  // hold M1=1050 for 500 ms
  m1 = 1050;
  Serial.println("[CMD] Safe Test: M1=1050 PWM for 500 ms");
}

// ----- Command receiver -----
void checkCommands() {
  int packetSize = commandUDP.parsePacket();
  if (packetSize <= 0) return;

  char buf[64];
  int len = commandUDP.read(buf, sizeof(buf) - 1);
  buf[len] = '\0';

  String cmd = String(buf);
  cmd.trim();

  if (cmd == "SAFE_TEST") {
    handleSafeTest();
  } else {
    Serial.printf("[CMD] Unknown command: %s\n", cmd.c_str());
  }
}

// ----- Setup -----
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- ESP32 Booting Up ---");

  WiFi.setSleep(false);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  Serial.printf("Connecting to WiFi: %s\n", ssid);

  int counter = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    if (++counter > 60) {
      Serial.println("\nWiFi timeout – rebooting...");
      ESP.restart();
    }
  }
  Serial.println("\nWiFi connected!");
  Serial.print("Local IP:     ");
  Serial.println(WiFi.localIP());
  Serial.print("Broadcast IP: ");
  Serial.println(WiFi.broadcastIP());

  broadcastUDP.begin(TELEMETRY_PORT);
  commandUDP.begin(COMMAND_PORT);
  Serial.printf("UDP telemetry broadcast: port %d\n", TELEMETRY_PORT);
  Serial.printf("UDP command listener:    port %d\n", COMMAND_PORT);
}

// ----- Loop -----
void loop() {
  checkCommands();

  // End safe-test pulse when timer expires
  if (safeTestEndTime > 0 && millis() > safeTestEndTime) {
    m1 = 1000;
    safeTestEndTime = 0;
    Serial.println("[CMD] Safe Test ended: M1 reset to 1000");
  }

  if (millis() - lastSendTime > 100) {
    String localIP = WiFi.localIP().toString();

    String json = "{\"roll\": "               + String(roll, 2)
                + ", \"pitch\": "             + String(pitch, 2)
                + ", \"yaw\": "               + String(yaw, 2)
                + ", \"m1\": "                + String(m1)
                + ", \"m2\": "                + String(m2)
                + ", \"m3\": "                + String(m3)
                + ", \"m4\": "                + String(m4)
                + ", \"voltage\": "           + String(voltage, 2)
                + ", \"batteryPercentage\": " + String(batteryPercentage)
                + ", \"esp32_ip\": \""        + localIP + "\"}";

    broadcastUDP.beginPacket(WiFi.broadcastIP(), TELEMETRY_PORT);
    broadcastUDP.print(json);
    broadcastUDP.endPacket();

    lastSendTime = millis();

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
}
