#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUDP.h>
#include <esp_wifi.h>
#include <WebSocketsServer.h>
#include <ArduinoJson.h>

#include "secrets_auto.h"

const char* ssid     = SECRETS_WIFI_SSID;
const char* password = SECRETS_WIFI_PASS;

const int WS_PORT     = 81;
const int BEACON_PORT = 4242;

const unsigned long TELEMETRY_INTERVAL_MS = 100;   // 10 Hz
const unsigned long BEACON_INTERVAL_MS    = 5000;
const unsigned long SOUND_TIMEOUT_MS      = 1000;  // stop motors if no TILT_SOUND for 1 s
const unsigned long RC_TIMEOUT_MS        = 500;   // stop motors if no RC packet for 500 ms
const unsigned long FC_TIMEOUT_MS         = 2000;  // mark FC disconnected after 2 s silence

// ── UART to Betaflight FC ──────────────────────────────────────────────────────
//   Wiring (ESP32-C3 SuperMini):
//     ESP32 GPIO 20 (RX1)  →  FC TX  (the TX pad on the FC UART port)
//     ESP32 GPIO 21 (TX1)  →  FC RX  (the RX pad on the FC UART port)
//     GND  ←→  GND  (shared ground required)
#define FC_RX_PIN  20
#define FC_TX_PIN  21
#define FC_BAUD    115200

HardwareSerial FCSerial(1);  // UART1

// ── MSP command codes ──────────────────────────────────────────────────────────
#define MSP_ATTITUDE  108   // response: roll, pitch (int16 × 10 = tenths of °), yaw (int16 = °)
#define MSP_ANALOG    110   // response: vbat (byte, 0.1 V/unit), mAh, rssi, amperage
#define MSP_SET_MOTOR 214   // request:  8 × uint16 motor values (PWM 1000–2000, 0 = off)

WebSocketsServer wsServer(WS_PORT);
WiFiUDP beaconUDP;

// ── Flight state ───────────────────────────────────────────────────────────────
enum FlightMode { MODE_IDLE, MODE_BALANCE, MODE_MANUAL, MODE_SOUND, MODE_RC };

bool       isArmed     = false;
FlightMode flightMode  = MODE_IDLE;
bool       simMode     = true;   // true = generate fake telemetry (demo when no FC wired)
bool       fcConnected = false;  // true once FC sends a valid MSP response

// Telemetry values (updated from FC via MSP, or simulation)
float roll      = 0.0f;
float pitch     = 0.0f;
float yaw       = 0.0f;
float increment = 0.5f;  // sim only

int   m1 = 1000, m2 = 1000, m3 = 1000, m4 = 1000;
float voltage           = 16.8f;
int   batteryPercentage = 100;

// ── Balance parameters ─────────────────────────────────────────────────────────
int   baseThrottle = 1200;
float kPRoll       = 10.0f;
float kPPitch      = 10.0f;

// ── RC mode parameters ─────────────────────────────────────────────────────────
float         rcTargetRoll     = 0.0f;  // target roll angle  (°, –45…45)
float         rcTargetPitch    = 0.0f;  // target pitch angle (°, –45…45)
float         rcYawAdj         = 0.0f;  // yaw PWM contribution (–100…100)
int           rcThrottle       = 1000;  // base throttle PWM
unsigned long lastRCPacketMs   = 0;

// ── Sound mode parameters ──────────────────────────────────────────────────────
int           targetSoundPWM    = 1000;
int           maxSoundPWM       = 1400;
unsigned long lastSoundPacketMs = 0;

unsigned long safeTestEndTime   = 0;
unsigned long lastTelemetryTime = 0;
unsigned long lastBeaconTime    = 0;
unsigned long lastFCPacketMs    = 0;  // timestamp of last valid MSP response from FC
unsigned long lastMspAttReqMs   = 0;  // timestamp of last MSP_ATTITUDE request
unsigned long lastMspAnlReqMs   = 0;  // timestamp of last MSP_ANALOG request
unsigned long lastDiagMs        = 0;  // diagnostic print interval

uint32_t fcRxByteCount = 0;           // total raw bytes received from FC (diagnostic)

// ── MSP parser state machine ───────────────────────────────────────────────────
enum MspParseState {
  MSP_IDLE_S, MSP_HEADER_M, MSP_HEADER_DIR,
  MSP_SIZE,   MSP_CMD,      MSP_PAYLOAD,    MSP_CHECKSUM
};

MspParseState mspParseState = MSP_IDLE_S;
uint8_t       mspSize       = 0;
uint8_t       mspCmd        = 0;
uint8_t       mspChecksum   = 0;
uint8_t       mspPayloadIdx = 0;
uint8_t       mspPayload[32];

// ── MSP: build and send a request frame ───────────────────────────────────────
void sendMSP(uint8_t cmd, uint8_t* data = nullptr, uint8_t n = 0) {
  uint8_t cs = n ^ cmd;
  for (int i = 0; i < n; i++) cs ^= data[i];
  FCSerial.write('$'); FCSerial.write('M'); FCSerial.write('<');
  FCSerial.write(n);   FCSerial.write(cmd);
  for (int i = 0; i < n; i++) FCSerial.write(data[i]);
  FCSerial.write(cs);
}

// ── MSP: handle a validated response ─────────────────────────────────────────
void processMSPResponse(uint8_t cmd, uint8_t* data, uint8_t size) {
  lastFCPacketMs = millis();
  fcConnected    = true;

  if (cmd == MSP_ATTITUDE && size >= 6) {
    // Betaflight encodes roll/pitch in tenths of a degree, yaw in whole degrees.
    int16_t r, p, y;
    memcpy(&r, data + 0, 2);
    memcpy(&p, data + 2, 2);
    memcpy(&y, data + 4, 2);
    roll  =  r / 10.0f;
    pitch =  p / 10.0f;
    yaw   = (float)y;
  }
  else if (cmd == MSP_ANALOG && size >= 1) {
    // Byte 0: vbat in units of 0.1 V  (e.g. 168 → 16.8 V for a full 4S pack)
    voltage = data[0] / 10.0f;
    batteryPercentage = constrain(
      (int)((voltage - 13.0f) / (16.8f - 13.0f) * 100.0f), 0, 100
    );
  }
}

// ── MSP: non-blocking byte-by-byte response parser ────────────────────────────
void readMSP() {
  while (FCSerial.available()) {
    uint8_t c = (uint8_t)FCSerial.read();
    fcRxByteCount++;
    switch (mspParseState) {
      case MSP_IDLE_S:
        if (c == '$') mspParseState = MSP_HEADER_M;
        break;
      case MSP_HEADER_M:
        mspParseState = (c == 'M') ? MSP_HEADER_DIR : MSP_IDLE_S;
        break;
      case MSP_HEADER_DIR:
        if (c == '>') mspParseState = MSP_SIZE;
        else          mspParseState = MSP_IDLE_S;
        break;
      case MSP_SIZE:
        mspSize = c; mspChecksum = c; mspPayloadIdx = 0;
        mspParseState = MSP_CMD;
        break;
      case MSP_CMD:
        mspCmd = c; mspChecksum ^= c;
        mspParseState = (mspSize > 0) ? MSP_PAYLOAD : MSP_CHECKSUM;
        break;
      case MSP_PAYLOAD:
        if (mspPayloadIdx < sizeof(mspPayload)) mspPayload[mspPayloadIdx] = c;
        mspChecksum ^= c;
        if (++mspPayloadIdx >= mspSize) mspParseState = MSP_CHECKSUM;
        break;
      case MSP_CHECKSUM:
        if (c == mspChecksum)
          processMSPResponse(mspCmd, mspPayload, mspSize);
        else
          Serial.printf("[MSP] Checksum error cmd=%u  got=0x%02X  exp=0x%02X\n",
                        mspCmd, c, mspChecksum);
        mspParseState = MSP_IDLE_S;
        break;
    }
  }
}

// ── MSP: push current m1-m4 to FC via MSP_SET_MOTOR ──────────────────────────
//   Betaflight interprets values < 1000 as motor-off; channels 5-8 unused on quad → 0.
void applyMotors() {
  auto clamp = [](int v) -> uint16_t {
    return (v < 1000) ? 0 : (uint16_t)constrain(v, 1000, 2000);
  };
  uint16_t motors[8] = { clamp(m1), clamp(m2), clamp(m3), clamp(m4), 0, 0, 0, 0 };
  sendMSP(MSP_SET_MOTOR, (uint8_t*)motors, 16);
}

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

// ── RC P-controller ───────────────────────────────────────────────────────────
// Same motor layout as BALANCE; target angles come from the phone instead of 0.
// X-layout: FL=CW, FR=CCW, RL=CCW, RR=CW — yaw mixes accordingly.
void runRCMode() {
  float rAdj = (rcTargetRoll  - roll)  * kPRoll;
  float pAdj = (rcTargetPitch - pitch) * kPPitch;
  int   yAdj = (int)rcYawAdj;
  m1 = constrain(rcThrottle + (int)rAdj - (int)pAdj - yAdj, 1000, 2000); // FL  CW
  m2 = constrain(rcThrottle - (int)rAdj - (int)pAdj + yAdj, 1000, 2000); // FR CCW
  m3 = constrain(rcThrottle + (int)rAdj + (int)pAdj + yAdj, 1000, 2000); // RL CCW
  m4 = constrain(rcThrottle - (int)rAdj + (int)pAdj - yAdj, 1000, 2000); // RR  CW
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const char* modeString() {
  switch (flightMode) {
    case MODE_BALANCE: return "BALANCE";
    case MODE_MANUAL:  return "MANUAL";
    case MODE_SOUND:   return "SOUND";
    case MODE_RC:      return "RC";
    default:           return "IDLE";
  }
}

void stopMotors() {
  m1 = m2 = m3 = m4 = 1000;
  applyMotors();
}

// ── Command handler ───────────────────────────────────────────────────────────
void handleCommand(const char* payload, size_t length) {
  String raw = String(payload).substring(0, length);
  raw.trim();

  // Plain-text shortcuts
  if (raw == "SAFE_TEST") {
    if (!isArmed) return;
    safeTestEndTime = millis() + 500;
    m1 = 1050;
    applyMotors();
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

  if (strcmp(cmd, "START_RC") == 0) {
    if (!isArmed) { Serial.println("[CMD] Not armed"); return; }
    if (doc["kPRoll"].is<float>())  kPRoll  = doc["kPRoll"].as<float>();
    if (doc["kPPitch"].is<float>()) kPPitch = doc["kPPitch"].as<float>();
    rcTargetRoll = rcTargetPitch = rcYawAdj = 0.0f;
    rcThrottle   = 1000;
    lastRCPacketMs = millis();
    flightMode = MODE_RC; simMode = false;
    Serial.printf("[CMD] START_RC kPR=%.2f kPP=%.2f\n", kPRoll, kPPitch);
    return;
  }

  if (strcmp(cmd, "RC") == 0) {
    if (!isArmed || flightMode != MODE_RC) return;
    if (doc["thr"].is<int>())   rcThrottle    = constrain(doc["thr"].as<int>(), 1000, 2000);
    if (doc["pit"].is<float>()) rcTargetPitch = constrain(doc["pit"].as<float>(), -45.0f, 45.0f);
    if (doc["rol"].is<float>()) rcTargetRoll  = constrain(doc["rol"].as<float>(), -45.0f, 45.0f);
    if (doc["yaw"].is<float>()) rcYawAdj      = constrain(doc["yaw"].as<float>(), -100.0f, 100.0f);
    lastRCPacketMs = millis();
    return;
  }

  if (strcmp(cmd, "START_BALANCE") == 0) {
    if (!isArmed) { Serial.println("[CMD] Not armed"); return; }
    if (doc["baseThrottle"].is<int>()) baseThrottle = doc["baseThrottle"].as<int>();
    if (doc["kPRoll"].is<float>())     kPRoll       = doc["kPRoll"].as<float>();
    if (doc["kPPitch"].is<float>())    kPPitch      = doc["kPPitch"].as<float>();
    flightMode = MODE_BALANCE; simMode = false;
    Serial.printf("[CMD] START_BALANCE thr=%d kPR=%.2f kPP=%.2f\n",
                  baseThrottle, kPRoll, kPPitch);
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
    applyMotors();
    Serial.println("[CMD] START_MANUAL");
    return;
  }

  // ── Sound mode ─────────────────────────────────────────────────────────────
  if (strcmp(cmd, "START_SOUND") == 0) {
    if (!isArmed) { Serial.println("[CMD] Not armed"); return; }
    if (doc["maxPWM"].is<int>())
      maxSoundPWM = constrain(doc["maxPWM"].as<int>(), 1000, 1500);
    flightMode        = MODE_SOUND;
    simMode           = false;
    lastSoundPacketMs = millis();
    targetSoundPWM    = 1000;
    stopMotors();
    Serial.printf("[CMD] START_SOUND maxPWM=%d\n", maxSoundPWM);
    return;
  }

  if (strcmp(cmd, "TILT_SOUND") == 0) {
    if (!isArmed || flightMode != MODE_SOUND) return;
    int pwm = doc["pwm"] | 1000;
    targetSoundPWM    = constrain(pwm, 1000, maxSoundPWM);
    lastSoundPacketMs = millis();
    m1 = m2 = m3 = m4 = targetSoundPWM;
    applyMotors();
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
    applyMotors();
  }
}

// ── WebSocket events ──────────────────────────────────────────────────────────
void onWsEvent(uint8_t num, WStype_t type, uint8_t* payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED:
      Serial.printf("[WS] #%u connected from %s\n",
                    num, wsServer.remoteIP(num).toString().c_str());
      break;
    case WStype_DISCONNECTED:
      Serial.printf("[WS] #%u disconnected\n", num);
      if (flightMode == MODE_SOUND || flightMode == MODE_RC) {
        stopMotors(); flightMode = MODE_IDLE;
      }
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

  // Start UART to Betaflight FC
  FCSerial.begin(FC_BAUD, SERIAL_8N1, FC_RX_PIN, FC_TX_PIN);
  Serial.printf("FC UART:   RX=GPIO%d  TX=GPIO%d  %d baud\n",
                FC_RX_PIN, FC_TX_PIN, FC_BAUD);

  WiFi.persistent(false);  // don't save credentials to NVS flash
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  // Accept 11b/g/n so iPhone hotspot (which can negotiate any of them) works
  esp_wifi_set_protocol(WIFI_IF_STA,
    WIFI_PROTOCOL_11B | WIFI_PROTOCOL_11G | WIFI_PROTOCOL_11N);

  // Scan so the user can see what's visible, but don't delay long afterwards –
  // iPhone hotspot drops its beacon fast when idle.
  Serial.println("Scanning for networks...");
  int n = WiFi.scanNetworks();
  Serial.printf("%d found:\n", n);
  for (int i = 0; i < n; ++i)
    Serial.printf("  %d: %s (RSSI:%d)\n", i+1, WiFi.SSID(i).c_str(), WiFi.RSSI(i));
  WiFi.scanDelete();

  // Retry loop: attempt up to 5 times before giving up and rebooting.
  // Each attempt waits up to 15 s (30 × 500 ms).
  bool connected = false;
  for (int attempt = 1; attempt <= 5 && !connected; attempt++) {
    Serial.printf("\nAttempt %d/5 – connecting to \"%s\" ", attempt, ssid);
    WiFi.begin(ssid, password);
    for (int i = 0; i < 30; i++) {
      delay(500); Serial.print(".");
      if (WiFi.status() == WL_CONNECTED) { connected = true; break; }
    }
    if (!connected) {
      Serial.printf(" failed (status=%d)\n", WiFi.status());
      WiFi.disconnect(false);
      delay(500);
    }
  }
  if (!connected) {
    Serial.println("\nAll attempts failed – rebooting");
    delay(1000);
    ESP.restart();
  }

  Serial.println("\nConnected!");
  Serial.print("IP:        "); Serial.println(WiFi.localIP());
  Serial.print("Broadcast: "); Serial.println(WiFi.broadcastIP());

  wsServer.begin();
  wsServer.onEvent(onWsEvent);
  Serial.printf("WebSocket on port %d\n", WS_PORT);

  beaconUDP.begin(BEACON_PORT);
  Serial.printf("Beacon on port %d every %lu s\n",
                BEACON_PORT, BEACON_INTERVAL_MS / 1000);
}

// ── Loop ──────────────────────────────────────────────────────────────────────
void loop() {
  wsServer.loop();
  unsigned long now = millis();

  // ── Poll FC for telemetry ──────────────────────────────────────────────────
  if (now - lastMspAttReqMs >= TELEMETRY_INTERVAL_MS) {
    sendMSP(MSP_ATTITUDE);            // request attitude at 10 Hz
    lastMspAttReqMs = now;
  }
  if (now - lastMspAnlReqMs >= 500) {
    sendMSP(MSP_ANALOG);              // request battery at 2 Hz
    lastMspAnlReqMs = now;
  }
  readMSP();                          // parse whatever the FC has sent back

  // Diagnostic: print FC status every 3 s so you can see what's happening in the serial monitor
  if (now - lastDiagMs >= 3000) {
    Serial.printf("[FC] connected=%s  rx_bytes=%lu  parse_state=%d  serial_avail=%d\n",
                  fcConnected ? "YES" : "NO",
                  (unsigned long)fcRxByteCount,
                  (int)mspParseState,
                  FCSerial.available());
    lastDiagMs = now;
  }

  // FC timeout → fall back to simulation mode
  if (fcConnected && (now - lastFCPacketMs > FC_TIMEOUT_MS)) {
    fcConnected = false;
    if (!isArmed) simMode = true;
    Serial.println("[FC] Timeout – no MSP for 2 s, simulation resuming");
  }

  // ── Safe-test timer ────────────────────────────────────────────────────────
  if (safeTestEndTime > 0 && now > safeTestEndTime) {
    m1 = 1000; safeTestEndTime = 0;
    applyMotors();
    Serial.println("[CMD] Safe Test ended");
  }

  // ── Sound mode: stop motors if iOS stops sending packets ───────────────────
  if (flightMode == MODE_SOUND && isArmed) {
    if (now - lastSoundPacketMs > SOUND_TIMEOUT_MS) {
      stopMotors();
      Serial.println("[SOUND] Timeout – motors stopped (no packet for 1 s)");
    }
  }

  // ── RC mode: stop if phone stops sending control packets ───────────────────
  if (flightMode == MODE_RC && isArmed) {
    if (now - lastRCPacketMs > RC_TIMEOUT_MS) {
      stopMotors(); flightMode = MODE_IDLE;
      Serial.println("[RC] Timeout – motors stopped");
    }
  }

  // ── Flight loop (10 Hz) ────────────────────────────────────────────────────
  if (now - lastTelemetryTime >= TELEMETRY_INTERVAL_MS) {

    if (isArmed) {
      if (flightMode == MODE_BALANCE) {
        runBalanceMode();
        applyMotors();
      }
      if (flightMode == MODE_RC) {
        runRCMode();
        applyMotors();
      }
      // MODE_SOUND:  applyMotors() called in TILT_SOUND handler
      // MODE_MANUAL: applyMotors() called in START_MANUAL handler
      // MODE_IDLE:   motors already at 1000 from stopMotors()
    }
    // Disarmed: motors stay at 1000 from the last stopMotors() / init; no periodic flood

    // Simulation: runs when FC not wired and drone not armed, for demo/dashboard
    if (simMode && !isArmed && !fcConnected) {
      roll  += increment; pitch += increment * 0.5f; yaw += increment * 0.2f;
      if (abs(roll) > 90.0f) increment = -increment;
      if (safeTestEndTime == 0) m1 = random(1100, 1800);
      m2 = random(1100, 1800); m3 = random(1100, 1800); m4 = random(1100, 1800);
      voltage -= 0.005f;
      if (voltage < 13.0f) voltage = 16.8f;
      batteryPercentage = constrain(
        (int)((voltage - 13.0f) / (16.8f - 13.0f) * 100.0f), 0, 100
      );
    }

    // Telemetry broadcast to iOS (10 Hz)
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
                + ",\"mode\":\""            + modeString()          + "\""
                + ",\"fc\":"                + (fcConnected ? "true" : "false")
                + "}";
    wsServer.broadcastTXT(json);
    lastTelemetryTime = now;
  }

  // UDP beacon
  if (now - lastBeaconTime > BEACON_INTERVAL_MS) {
    String beacon = "EASYPILOT:" + WiFi.localIP().toString();
    beaconUDP.beginPacket(WiFi.broadcastIP(), BEACON_PORT);
    beaconUDP.print(beacon);
    beaconUDP.endPacket();
    Serial.printf("[Beacon] %s  armed=%s  mode=%s  fc=%s\n",
                  beacon.c_str(),
                  isArmed     ? "YES" : "NO",
                  modeString(),
                  fcConnected ? "YES" : "NO");
    lastBeaconTime = now;
  }
}
