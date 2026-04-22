#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUDP.h>
#include <WebSocketsServer.h>
#include <ArduinoJson.h>

#include "secrets_auto.h"

const char* ssid     = SECRETS_WIFI_SSID;
const char* password = SECRETS_WIFI_PASS;

const int WS_PORT     = 81;
const int BEACON_PORT = 4242;

const unsigned long TELEMETRY_INTERVAL_MS = 100;
const unsigned long BEACON_INTERVAL_MS    = 5000;
const unsigned long SOUND_TIMEOUT_MS      = 1000; // stop motors if no TILT_SOUND for 1 s

WebSocketsServer wsServer(WS_PORT);
WiFiUDP beaconUDP;

// ── Flight state ──────────────────────────────────────────────────────────────
enum FlightMode { MODE_IDLE, MODE_BALANCE, MODE_MANUAL, MODE_SOUND };

bool       isArmed    = false;
FlightMode flightMode = MODE_IDLE;
bool       simMode    = true;

// Telemetry values
float roll      = 0.0f;
float pitch     = 0.0f;
float yaw       = 0.0f;
float increment = 0.5f;

int   m1 = 1000, m2 = 1000, m3 = 1000, m4 = 1000;
float voltage           = 16.8f;
int   batteryPercentage = 100;

// ── Balance parameters ────────────────────────────────────────────────────────
int   baseThrottle = 1200;
float kPRoll       = 10.0f;
float kPPitch      = 10.0f;

// ── Sound mode parameters ─────────────────────────────────────────────────────
int           targetSoundPWM    = 1000;          // set by each TILT_SOUND packet
int           maxSoundPWM       = 1400;          // cap received from iOS on START_SOUND
unsigned long lastSoundPacketMs = 0;             // for 1-second timeout

unsigned long safeTestEndTime   = 0;
unsigned long lastTelemetryTime = 0;
unsigned long lastBeaconTime    = 0;

// ── Balance P-controller ──────────────────────────────────────────────────────
// Quad-X layout (top view):  M1(FL) M2(FR) / M3(RL) M4(RR)
void runBalanceMode() {
  float rAdj = (0.0f - roll)  * kPRoll;
  float pAdj = (0.0f - pitch) * kPPitch;
  m1 = constrain(baseThrottle + (int)rAdj - (int)pAdj, 1000, 2000); // FL
  m2 = constrain(baseThrottle - (int)rAdj - (int)pAdj, 1000, 2000); // FR
  m3 = constrain(baseThrottle + (int)rAdj + (int)pAdj, 1000, 2000); // RL
  m4 = constrain(baseThrottle - (int)rAdj + (int)pAdj, 1000, 2000); // RR
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const char* modeString() {
  switch (flightMode) {
    case MODE_BALANCE: return "BALANCE";
    case MODE_MANUAL:  return "MANUAL";
    case MODE_SOUND:   return "SOUND";
    default:           return "IDLE";
  }
}

void stopMotors() { m1 = m2 = m3 = m4 = 1000; }

// ── Command handler ───────────────────────────────────────────────────────────
void handleCommand(const char* payload, size_t length) {
  String raw = String(payload).substring(0, length);
  raw.trim();

  // Plain-text shortcuts
  if (raw == "SAFE_TEST") {
    if (!isArmed) return;
    safeTestEndTime = millis() + 500;
    m1 = 1050;
    Serial.println("[CMD] Safe Test 500 ms");
    return;
  }
  if (raw == "SIMULATE") {
    simMode = true;
    Serial.println("[CMD] Simulation ON");
    return;
  }

  // JSON commands
  JsonDocument doc;
  if (deserializeJson(doc, raw) != DeserializationError::Ok) {
    Serial.printf("[CMD] Bad payload: %s\n", raw.c_str());
    return;
  }

  const char* cmd = doc["cmd"] | "";

  if (strcmp(cmd, "ARM") == 0) {
    isArmed = true;
    Serial.println("[CMD] ARMED");
    return;
  }

  if (strcmp(cmd, "DISARM") == 0) {
    isArmed = false; flightMode = MODE_IDLE;
    stopMotors();
    Serial.println("[CMD] DISARMED");
    return;
  }

  if (strcmp(cmd, "STOP") == 0) {
    flightMode = MODE_IDLE;
    stopMotors();
    Serial.println("[CMD] STOP");
    return;
  }

  if (strcmp(cmd, "START_BALANCE") == 0) {
    if (!isArmed) { Serial.println("[CMD] Not armed"); return; }
    if (doc["baseThrottle"].is<int>()) baseThrottle = doc["baseThrottle"].as<int>();
    if (doc["kPRoll"].is<float>())     kPRoll       = doc["kPRoll"].as<float>();
    if (doc["kPPitch"].is<float>())    kPPitch      = doc["kPPitch"].as<float>();
    flightMode = MODE_BALANCE; simMode = false;
    Serial.printf("[CMD] START_BALANCE thr=%d kPR=%.2f kPP=%.2f\n", baseThrottle, kPRoll, kPPitch);
    return;
  }

  if (strcmp(cmd, "START_MANUAL") == 0) {
    if (!isArmed) { Serial.println("[CMD] Not armed"); return; }
    if (doc["roll"].is<float>())            roll              = doc["roll"].as<float>();
    if (doc["pitch"].is<float>())           pitch             = doc["pitch"].as<float>();
    if (doc["yaw"].is<float>())             yaw               = doc["yaw"].as<float>();
    if (doc["m1"].is<int>())                m1                = doc["m1"].as<int>();
    if (doc["m2"].is<int>())                m2                = doc["m2"].as<int>();
    if (doc["m3"].is<int>())                m3                = doc["m3"].as<int>();
    if (doc["m4"].is<int>())                m4                = doc["m4"].as<int>();
    if (doc["voltage"].is<float>())         voltage           = doc["voltage"].as<float>();
    if (doc["batteryPercentage"].is<int>()) batteryPercentage = doc["batteryPercentage"].as<int>();
    flightMode = MODE_MANUAL; simMode = false;
    Serial.println("[CMD] START_MANUAL");
    return;
  }

  // ── Sound mode ────────────────────────────────────────────────────────────
  if (strcmp(cmd, "START_SOUND") == 0) {
    if (!isArmed) { Serial.println("[CMD] Not armed"); return; }
    if (doc["maxPWM"].is<int>()) maxSoundPWM = constrain(doc["maxPWM"].as<int>(), 1000, 1500);
    flightMode         = MODE_SOUND;
    simMode            = false;
    lastSoundPacketMs  = millis(); // reset timeout
    targetSoundPWM     = 1000;
    stopMotors();
    Serial.printf("[CMD] START_SOUND maxPWM=%d\n", maxSoundPWM);
    return;
  }

  if (strcmp(cmd, "TILT_SOUND") == 0) {
    if (!isArmed || flightMode != MODE_SOUND) return;
    int pwm = doc["pwm"] | 1000;
    targetSoundPWM    = constrain(pwm, 1000, maxSoundPWM); // enforce cap on ESP32 side too
    lastSoundPacketMs = millis();
    m1 = m2 = m3 = m4 = targetSoundPWM;
    return;
  }

  // No "cmd" → telemetry value override
  if (doc["cmd"].isNull()) {
    if (doc["roll"].is<float>())            roll              = doc["roll"].as<float>();
    if (doc["pitch"].is<float>())           pitch             = doc["pitch"].as<float>();
    if (doc["yaw"].is<float>())             yaw               = doc["yaw"].as<float>();
    if (doc["m1"].is<int>())                m1                = doc["m1"].as<int>();
    if (doc["m2"].is<int>())                m2                = doc["m2"].as<int>();
    if (doc["m3"].is<int>())                m3                = doc["m3"].as<int>();
    if (doc["m4"].is<int>())                m4                = doc["m4"].as<int>();
    if (doc["voltage"].is<float>())         voltage           = doc["voltage"].as<float>();
    if (doc["batteryPercentage"].is<int>()) batteryPercentage = doc["batteryPercentage"].as<int>();
    simMode = false;
  }
}

// ── WebSocket events ──────────────────────────────────────────────────────────
void onWsEvent(uint8_t num, WStype_t type, uint8_t* payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED:
      Serial.printf("[WS] #%u connected from %s\n", num, wsServer.remoteIP(num).toString().c_str());
      break;
    case WStype_DISCONNECTED:
      Serial.printf("[WS] #%u disconnected\n", num);
      // Safety: if drone was in sound mode, stop motors
      if (flightMode == MODE_SOUND) { stopMotors(); flightMode = MODE_IDLE; }
      break;
    case WStype_TEXT:
      handleCommand((const char*)payload, length);
      break;
    default: break;
  }
}

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- ESP32 EasyPilot Booting ---");

  WiFi.setSleep(false);
  WiFi.mode(WIFI_STA);

  Serial.println("Scanning for networks...");
  int n = WiFi.scanNetworks();
  Serial.printf("%d found:\n", n);
  for (int i = 0; i < n; ++i) {
    Serial.printf("  %d: %s (RSSI:%d)\n", i+1, WiFi.SSID(i).c_str(), WiFi.RSSI(i));
    delay(10);
  }

  WiFi.begin(ssid, password);
  Serial.printf("\nConnecting to %s ", ssid);
  int counter = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
    if (++counter > 60) { Serial.println("\nTimeout – rebooting"); ESP.restart(); }
  }

  Serial.println("\nConnected!");
  Serial.print("IP:        "); Serial.println(WiFi.localIP());
  Serial.print("Broadcast: "); Serial.println(WiFi.broadcastIP());

  wsServer.begin();
  wsServer.onEvent(onWsEvent);
  Serial.printf("WebSocket on port %d\n", WS_PORT);

  beaconUDP.begin(BEACON_PORT);
  Serial.printf("Beacon on port %d every %lu s\n", BEACON_PORT, BEACON_INTERVAL_MS / 1000);
}

// ── Loop ──────────────────────────────────────────────────────────────────────
void loop() {
  wsServer.loop();
  unsigned long now = millis();

  // Safe-test timer
  if (safeTestEndTime > 0 && now > safeTestEndTime) {
    m1 = 1000; safeTestEndTime = 0;
    Serial.println("[CMD] Safe Test ended");
  }

  // Sound mode: stop motors if iOS stops sending packets
  if (flightMode == MODE_SOUND && isArmed) {
    if (now - lastSoundPacketMs > SOUND_TIMEOUT_MS) {
      stopMotors();
      Serial.println("[SOUND] Timeout – motors stopped (no packet for 1 s)");
      // Stay in SOUND mode; will resume when packets arrive again
    }
  }

  // Flight loop (10 Hz)
  if (now - lastTelemetryTime > TELEMETRY_INTERVAL_MS) {

    if (isArmed) {
      if      (flightMode == MODE_BALANCE) runBalanceMode();
      // MODE_SOUND:  motors already set by TILT_SOUND handler
      // MODE_MANUAL: motors already set by START_MANUAL / override
    }

    // Advance simulation only when disarmed
    if (simMode && !isArmed) {
      roll  += increment; pitch += increment * 0.5f; yaw += increment * 0.2f;
      if (abs(roll) > 90.0f) increment = -increment;
      if (safeTestEndTime == 0) m1 = random(1100, 1800);
      m2 = random(1100, 1800); m3 = random(1100, 1800); m4 = random(1100, 1800);
      voltage -= 0.005f;
      if (voltage < 13.0f) voltage = 16.8f;
      batteryPercentage = constrain((int)((voltage - 13.0f) / (16.8f - 13.0f) * 100.0f), 0, 100);
    }

    // Telemetry broadcast
    String json = "{\"roll\":"              + String(roll, 2)
                + ",\"pitch\":"             + String(pitch, 2)
                + ",\"yaw\":"               + String(yaw, 2)
                + ",\"m1\":"                + String(m1)
                + ",\"m2\":"                + String(m2)
                + ",\"m3\":"                + String(m3)
                + ",\"m4\":"                + String(m4)
                + ",\"voltage\":"           + String(voltage, 2)
                + ",\"batteryPercentage\":" + String(batteryPercentage)
                + ",\"armed\":"             + (isArmed ? "true" : "false")
                + ",\"mode\":\""            + modeString() + "\"}";
    wsServer.broadcastTXT(json);
    lastTelemetryTime = now;
  }

  // UDP beacon
  if (now - lastBeaconTime > BEACON_INTERVAL_MS) {
    String beacon = "EASYPILOT:" + WiFi.localIP().toString();
    beaconUDP.beginPacket(WiFi.broadcastIP(), BEACON_PORT);
    beaconUDP.print(beacon);
    beaconUDP.endPacket();
    Serial.printf("[Beacon] %s  armed=%s  mode=%s\n",
                  beacon.c_str(), isArmed ? "YES" : "NO", modeString());
    lastBeaconTime = now;
  }
}
