#include <WiFi.h>
#include <WebServer.h>
#include <esp_wifi.h>
#include <ArduinoOTA.h>

// ============================================================
// 1. EINSTELLUNGEN
// ============================================================
const char* ssid = "Dav";
const char* password = "12345678";

#define FC_TX_PIN 21
#define FC_RX_PIN 20
#define FC_BAUD 115200

// ------------------------------------------------------------
// CASCADED PID (Betaflight/ArduPilot/PX4 style)
//   OUTER angle loop (slow, P-only): angle_err -> rate_setpoint
//   INNER rate loop  (fast, full PID, derivative on measurement,
//                     low-pass filtered D, anti-windup I)
// ------------------------------------------------------------

// Outer loop: deg/s of desired angular rate per deg of angle error.
// Higher = stiffer response, but more overshoot / oscillation.
float KP_ANGLE       = 4.5f;
float MAX_RATE_DEG_S = 120.0f;   // saturate desired rate (safer)

// Inner loop gains (operate on gyro rate in deg/s, output in PWM units).
// Conservative starting point — tune up only after verifying stability.
float KP_RATE = 0.55f;
float KI_RATE = 0.40f;
float KD_RATE = 0.012f;

// First-order low-pass on D-term. Lower Hz = smoother, more lag.
float D_LPF_HZ = 30.0f;

// Anti-windup integral clamp (PWM-equivalent units before KI multiply).
float I_LIMIT = 80.0f;

// Per-axis correction clamp — prevents one axis saturating motors.
float MAX_PID_OUTPUT = 150.0f;

// Throttle slew limit (PWM units / second). Stops base-throttle steps.
float THROTTLE_SLEW_PER_S = 250.0f;

// MSP_RAW_IMU gyro scaling. Many FC firmwares ship gyro as 1/4 dps per LSB.
// If your drone over/under-reacts on the rate loop, retune this first.
float GYRO_SCALE_DPS = 0.25f;

int   MAX_THROTTLE  = 1400;
float ACC_1G_VALUE  = 512.0f;

// ============================================================
// 2. GLOBALE VARIABLEN
// ============================================================
WebServer server(80);
bool isRunning = false;

// 0=Aus, 1=Takeoff(Zeit), 2=Hover, 3=Takeoff(Acc), -1=Failsafe, -2=Crash
int drone_state = 0;
unsigned long takeoff_start_time = 0;
unsigned long last_heartbeat = 0;

int hover_throttle   = 1050;
int takeoff_throttle = 1150;
int takeoff_time_ms  = 300;

// Attitude (deg) — from MSP_ATTITUDE @ 50 Hz
float currentRoll  = 0.0f;
float currentPitch = 0.0f;

// Body rates (deg/s) — from MSP_RAW_IMU gyro
float gyroRollDps  = 0.0f;
float gyroPitchDps = 0.0f;

int16_t currentAccZ = 0;

float estimated_vel_m_s   = 0.0f;
float estimated_height_m  = 0.0f;

int current_m1 = 0, current_m2 = 0, current_m3 = 0, current_m4 = 0;

// Inner-loop PID state
float i_roll  = 0.0f, i_pitch  = 0.0f;
float d_roll_lpf = 0.0f, d_pitch_lpf = 0.0f;
float prev_gyro_roll = 0.0f, prev_gyro_pitch = 0.0f;
unsigned long last_pid_us = 0;

// Slew-limited base throttle target
float base_throttle_smooth = 1000.0f;

// "Fresh sample" flag — PID runs synchronized to sensor arrivals
volatile bool fresh_gyro = false;

HardwareSerial FCSerial(1);

// ============================================================
// 3. MSP PROTOKOLL
// ============================================================
void sendMSP(uint8_t cmd, uint8_t *data, uint8_t n_bytes) {
  uint8_t checksum = 0;
  FCSerial.write('$'); FCSerial.write('M'); FCSerial.write('<');
  FCSerial.write(n_bytes); checksum ^= n_bytes;
  FCSerial.write(cmd);     checksum ^= cmd;
  for (int i = 0; i < n_bytes; i++) {
    FCSerial.write(data[i]);
    checksum ^= data[i];
  }
  FCSerial.write(checksum);
}

void setMotors(int m1, int m2, int m3, int m4) {
  // Below 1000 = hard OFF for Betaflight
  m1 = (m1 < 1000) ? 0 : constrain(m1, 1000, MAX_THROTTLE);
  m2 = (m2 < 1000) ? 0 : constrain(m2, 1000, MAX_THROTTLE);
  m3 = (m3 < 1000) ? 0 : constrain(m3, 1000, MAX_THROTTLE);
  m4 = (m4 < 1000) ? 0 : constrain(m4, 1000, MAX_THROTTLE);

  current_m1 = m1; current_m2 = m2;
  current_m3 = m3; current_m4 = m4;

  uint16_t motors[8] = {
    (uint16_t)m1, (uint16_t)m2,
    (uint16_t)m3, (uint16_t)m4,
    0, 0, 0, 0
  };
  sendMSP(214, (uint8_t*)motors, 16);
}

void readMSPResponse() {
  while (FCSerial.available() >= 6) {
    if (FCSerial.read() == '$' && FCSerial.read() == 'M' && FCSerial.read() == '>') {
      uint8_t size = FCSerial.read();
      uint8_t cmd  = FCSerial.read();

      if (cmd == 108 && size == 6) {
        // MSP_ATTITUDE: roll/pitch in 1/10 deg, yaw in deg
        int16_t roll, pitch, yaw;
        FCSerial.readBytes((char*)&roll,  2);
        FCSerial.readBytes((char*)&pitch, 2);
        FCSerial.readBytes((char*)&yaw,   2);
        FCSerial.read(); // checksum
        currentRoll  = roll  / 10.0f;
        currentPitch = pitch / 10.0f;
      }
      else if (cmd == 102 && size == 18) {
        // MSP_RAW_IMU: acc[3] + gyro[3] + mag[3], int16 each = 18 bytes
        int16_t accX, accY, accZ;
        int16_t gyrX, gyrY, gyrZ;
        int16_t magX, magY, magZ;
        FCSerial.readBytes((char*)&accX, 2);
        FCSerial.readBytes((char*)&accY, 2);
        FCSerial.readBytes((char*)&accZ, 2);
        FCSerial.readBytes((char*)&gyrX, 2);
        FCSerial.readBytes((char*)&gyrY, 2);
        FCSerial.readBytes((char*)&gyrZ, 2);
        FCSerial.readBytes((char*)&magX, 2);
        FCSerial.readBytes((char*)&magY, 2);
        FCSerial.readBytes((char*)&magZ, 2);
        FCSerial.read(); // checksum

        currentAccZ  = accZ;
        // Body axes: gyrX = roll-rate, gyrY = pitch-rate (Betaflight convention).
        gyroRollDps  = gyrX * GYRO_SCALE_DPS;
        gyroPitchDps = gyrY * GYRO_SCALE_DPS;
        fresh_gyro   = true;
      }
      else {
        for (int i = 0; i <= size; i++) FCSerial.read();
      }
    }
  }
}

// ============================================================
// 4. CASCADED PID
// ============================================================
void resetPidState() {
  i_roll = 0.0f; i_pitch = 0.0f;
  d_roll_lpf = 0.0f; d_pitch_lpf = 0.0f;
  prev_gyro_roll  = gyroRollDps;
  prev_gyro_pitch = gyroPitchDps;
  base_throttle_smooth = 1000.0f;
  last_pid_us = micros();
}

// Single-axis inner-loop PID with derivative-on-measurement + D-LPF + I clamp.
float ratePid(float rate_sp, float rate_meas, float &i_state,
              float &d_lpf, float &prev_meas, float dt) {
  float err = rate_sp - rate_meas;

  // Integrator (clamped — simple anti-windup)
  i_state += err * dt;
  i_state = constrain(i_state, -I_LIMIT, I_LIMIT);

  // Derivative on measurement (NOT on error) — eliminates derivative kick
  // when setpoint changes (e.g. takeoff -> hover transitions).
  float d_raw = -(rate_meas - prev_meas) / dt;
  prev_meas = rate_meas;

  // First-order low-pass on D term — suppresses gyro noise amplification.
  float rc    = 1.0f / (2.0f * 3.14159265f * D_LPF_HZ);
  float alpha = dt / (dt + rc);
  d_lpf += alpha * (d_raw - d_lpf);

  float out = KP_RATE * err + KI_RATE * i_state + KD_RATE * d_lpf;
  return constrain(out, -MAX_PID_OUTPUT, MAX_PID_OUTPUT);
}

void runStabilization(float dt) {
  // ---- OUTER LOOP: angle error -> rate setpoint (deg/s) ----
  float roll_err  = 0.0f - currentRoll;
  float pitch_err = 0.0f - currentPitch;

  float rate_sp_roll  = constrain(KP_ANGLE * roll_err,  -MAX_RATE_DEG_S, MAX_RATE_DEG_S);
  float rate_sp_pitch = constrain(KP_ANGLE * pitch_err, -MAX_RATE_DEG_S, MAX_RATE_DEG_S);

  // ---- INNER LOOP: rate error -> motor delta (PWM units) ----
  float roll_out  = ratePid(rate_sp_roll,  gyroRollDps,
                            i_roll,  d_roll_lpf,  prev_gyro_roll,  dt);
  float pitch_out = ratePid(rate_sp_pitch, gyroPitchDps,
                            i_pitch, d_pitch_lpf, prev_gyro_pitch, dt);

  // ---- BASE THROTTLE WITH STATE MACHINE + SLEW LIMIT ----
  int target_base = 1000;
  if (drone_state == 1) {
    target_base = takeoff_throttle;
    if (millis() - takeoff_start_time >= (unsigned long)takeoff_time_ms) drone_state = 2;
  }
  else if (drone_state == 3) {
    target_base = takeoff_throttle;
    float linear_accel = (currentAccZ / ACC_1G_VALUE) * 9.81f - 9.81f;
    if (fabs(linear_accel) < 0.1f) linear_accel = 0.0f;
    estimated_vel_m_s   += linear_accel * dt;
    estimated_height_m  += estimated_vel_m_s * dt;
    if (estimated_height_m >= 0.18f || (millis() - takeoff_start_time >= 2000)) {
      drone_state = 2;
    }
  }
  else if (drone_state == 2) {
    target_base = hover_throttle;
  }

  float max_step = THROTTLE_SLEW_PER_S * dt;
  float diff     = (float)target_base - base_throttle_smooth;
  base_throttle_smooth += constrain(diff, -max_step, max_step);

  // ---- X-CONFIG MIXER (preserved sign convention) ----
  float m1 = base_throttle_smooth - roll_out + pitch_out;
  float m2 = base_throttle_smooth - roll_out - pitch_out;
  float m3 = base_throttle_smooth + roll_out + pitch_out;
  float m4 = base_throttle_smooth + roll_out - pitch_out;

  setMotors((int)m1, (int)m2, (int)m3, (int)m4);
}

// ============================================================
// 5. DASHBOARD
// ============================================================
const char* htmlDashboard = R"rawliteral(
<!DOCTYPE html><html><head>
<meta charset='UTF-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<style>
body{font-family:sans-serif;text-align:center;background:#222;color:#fff;}
.box{background:#333;padding:15px;border-radius:8px;margin:10px;}
button{padding:15px;width:90%;margin:5px;border-radius:5px;border:none;font-weight:bold;cursor:pointer;}
.btn-start{background:#28a745;color:white;}
.btn-start-acc{background:#007bff;color:white;}
.btn-stop{background:#dc3545;color:white;}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
hr{border: 1px solid #555; margin: 15px 0;}
.alert{color:#ff4d4d; font-weight:bold;}
</style></head><body>

<h2>FC Dashboard (Diplomarbeit)</h2>

<div class='box'>
Status: <strong id='status'>-</strong><br>
Phase: <strong id='phase'>-</strong><br>
Roll: <span id='roll'>0</span>&deg; | Pitch: <span id='pitch'>0</span>&deg;<br>
est. Hoehe (Acc): <strong style="color:#00ffcc"><span id='height'>0.00</span> cm</strong>
</div>

<div class='box'>
<h3>Motoren (Max 1400)</h3>
<div class='grid'>
<div>M4: <span id='m4'>-</span></div>
<div>M2: <span id='m2'>-</span></div>
<div>M3: <span id='m3'>-</span></div>
<div>M1: <span id='m1'>-</span></div>
</div>
</div>

<div class='box'>
<b>Flug-Parameter</b><br><br>
Schwebegas (Hover): <span id='hv'>1050</span><br>
<input type='range' min='1050' max='1400' value='1050' style='width:90%'
oninput='fetch("/set_hover?val="+this.value);document.getElementById("hv").innerText=this.value'>
<hr>
Start-Gas (Takeoff Kick): <span id='tv'>1150</span><br>
<input type='range' min='1050' max='1400' value='1150' style='width:90%'
oninput='fetch("/set_takeoff_thr?val="+this.value);document.getElementById("tv").innerText=this.value'>
<hr>
Start-Dauer (nur Zeit-Modus): <span id='ttv'>300</span> ms<br>
<input type='range' min='0' max='1000' value='300' style='width:90%'
oninput='fetch("/set_takeoff_time?val="+this.value);document.getElementById("ttv").innerText=this.value'>
</div>

<button class='btn-start' onclick='startSequence("/start_time")'>START (ZEIT)</button>
<button class='btn-start-acc' onclick='startSequence("/start_acc")'>START (ACCELEROMETER 18cm)</button>
<button class='btn-stop' onclick='fetch("/stop")'>NOT-AUS / RESET</button>

<script>
function startSequence(endpoint) {
  fetch(endpoint).then(async r => {
    if(!r.ok) {
      let msg = await r.text();
      alert("START ABGEBROCHEN: " + msg);
    }
  });
}

setInterval(() => { fetch('/heartbeat').catch(()=>{}); }, 500);

setInterval(() => {
  fetch('/data').then(r=>r.json()).then(d=>{
    let statEl = document.getElementById('status');
    if(d.state === -1) statEl.innerHTML = "<span class='alert'>VERBINDUNG VERLOREN</span>";
    else if(d.state === -2) statEl.innerHTML = "<span class='alert'>CRASH (GEKIPPT)</span>";
    else statEl.innerText = d.running ? "AKTIV" : "GESTOPPT";

    let phaseText = "IDLE";
    if(d.state === 1) phaseText = "TAKEOFF (ZEIT)";
    if(d.state === 3) phaseText = "TAKEOFF (ACC)";
    if(d.state === 2) phaseText = "HOVER";
    document.getElementById('phase').innerText = phaseText;

    document.getElementById('roll').innerText   = d.roll;
    document.getElementById('pitch').innerText  = d.pitch;
    document.getElementById('height').innerText = (d.height * 100).toFixed(2);
    document.getElementById('m1').innerText     = d.m1;
    document.getElementById('m2').innerText     = d.m2;
    document.getElementById('m3').innerText     = d.m3;
    document.getElementById('m4').innerText     = d.m4;
  });
}, 200);
</script>

</body></html>
)rawliteral";

// ============================================================
// 6. SETUP
// ============================================================
bool connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true);
  delay(2000);
  WiFi.setTxPower(WIFI_POWER_8_5dBm);
  esp_wifi_set_protocol(WIFI_IF_STA, WIFI_PROTOCOL_11B | WIFI_PROTOCOL_11G | WIFI_PROTOCOL_11N);
  WiFi.begin(ssid, password);
  Serial.print("[WiFi] Connecting to "); Serial.println(ssid);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("[WiFi] CONNECTED  IP: http://");
    Serial.println(WiFi.localIP());
    Serial.print("[WiFi] RSSI: "); Serial.print(WiFi.RSSI()); Serial.println(" dBm");
    return true;
  }
  Serial.println("[WiFi] FAILED");
  return false;
}

void setup() {
  Serial.begin(115200);
  FCSerial.begin(FC_BAUD, SERIAL_8N1, FC_RX_PIN, FC_TX_PIN);

  while (!connectWiFi()) delay(5000);

  ArduinoOTA.setHostname("ESP32-Drohne");
  ArduinoOTA.setPassword("admin123");
  ArduinoOTA.onStart([]() { isRunning = false; drone_state = 0; setMotors(0, 0, 0, 0); });
  ArduinoOTA.begin();

  server.on("/", []() { server.send(200, "text/html", htmlDashboard); });
  server.on("/heartbeat", []() { last_heartbeat = millis(); server.send(200); });

  server.on("/start_time", []() {
    if (fabs(currentRoll) > 5.0f || fabs(currentPitch) > 5.0f) {
      server.send(400, "text/plain", "Drohne nicht flach!"); return;
    }
    isRunning = true;
    drone_state = 1;
    takeoff_start_time = millis();
    last_heartbeat     = millis();
    resetPidState();
    server.send(200);
  });

  server.on("/start_acc", []() {
    if (fabs(currentRoll) > 5.0f || fabs(currentPitch) > 5.0f) {
      server.send(400, "text/plain", "Drohne nicht flach!"); return;
    }
    isRunning = true;
    drone_state = 3;
    takeoff_start_time = millis();
    last_heartbeat     = millis();
    estimated_vel_m_s  = 0.0f;
    estimated_height_m = 0.0f;
    resetPidState();
    server.send(200);
  });

  server.on("/stop", []() {
    isRunning = false; drone_state = 0;
    estimated_vel_m_s = 0; estimated_height_m = 0;
    setMotors(0, 0, 0, 0);
    base_throttle_smooth = 1000.0f;
    server.send(200);
  });

  server.on("/set_hover",        []() { hover_throttle   = server.arg("val").toInt(); server.send(200); });
  server.on("/set_takeoff_thr",  []() { takeoff_throttle = server.arg("val").toInt(); server.send(200); });
  server.on("/set_takeoff_time", []() { takeoff_time_ms  = server.arg("val").toInt(); server.send(200); });

  server.on("/data", []() {
    String j = "{";
    j += "\"running\":" + String(isRunning ? "true" : "false") + ",";
    j += "\"state\":"   + String(drone_state)  + ",";
    j += "\"roll\":"    + String(currentRoll)  + ",";
    j += "\"pitch\":"   + String(currentPitch) + ",";
    j += "\"height\":"  + String(estimated_height_m, 4) + ",";
    j += "\"m1\":"      + String(current_m1)   + ",";
    j += "\"m2\":"      + String(current_m2)   + ",";
    j += "\"m3\":"      + String(current_m3)   + ",";
    j += "\"m4\":"      + String(current_m4);
    j += "}";
    server.send(200, "application/json", j);
  });

  server.begin();
}

// ============================================================
// LOOP
// ============================================================
void loop() {
  server.handleClient();
  ArduinoOTA.handle();

  if (WiFi.status() != WL_CONNECTED) connectWiFi();

  // Reprint the dashboard URL every 5s so you can grab it from the serial
  // monitor at any time without rebooting.
  static unsigned long last_ip_print = 0;
  if (WiFi.status() == WL_CONNECTED && millis() - last_ip_print > 5000) {
    Serial.print("[WEB] Dashboard: http://");
    Serial.println(WiFi.localIP());
    last_ip_print = millis();
  }

  // Request fresh attitude + IMU at 50 Hz
  static unsigned long last_msp_req = 0;
  if (millis() - last_msp_req > 20) {
    sendMSP(108, NULL, 0);   // MSP_ATTITUDE
    sendMSP(102, NULL, 0);   // MSP_RAW_IMU (acc + gyro + mag)
    last_msp_req = millis();
  }
  readMSPResponse();

  // ---- SAFETY FAILSAFES ----
  if (isRunning && (millis() - last_heartbeat > 1500)) {
    isRunning = false; drone_state = -1;
    setMotors(0, 0, 0, 0);
  }
  if (isRunning && (fabs(currentRoll) > 60.0f || fabs(currentPitch) > 60.0f)) {
    isRunning = false; drone_state = -2;
    setMotors(0, 0, 0, 0);
  }

  if (isRunning) {
    // Run PID *only* on fresh gyro samples — synchronized to sensor cadence.
    // Prevents the controller from operating on stale data (which is the
    // root cause of the "kicking" in the previous loop@200Hz / data@50Hz).
    if (fresh_gyro) {
      unsigned long now = micros();
      float dt = (now - last_pid_us) / 1000000.0f;
      if (dt <= 0.0f || dt > 0.1f) dt = 0.02f; // sanity
      last_pid_us = now;
      fresh_gyro  = false;
      runStabilization(dt);
    }
  } else {
    // Periodically resend "off" — guards against transient MSP losses.
    static unsigned long lastStop = 0;
    if (millis() - lastStop > 200) {
      setMotors(0, 0, 0, 0);
      lastStop = millis();
    }
  }
}
