#include <WiFi.h>
#include <WebServer.h>
#include <esp_wifi.h>
#include <ArduinoOTA.h>

// ============================================================
// 1. EINSTELLUNGEN
// ============================================================
const char* ssid = "Sim";
const char* password = "123456789";

#define FC_TX_PIN 21
#define FC_RX_PIN 20
#define FC_BAUD 115200

float KP = 1.5;
float KI = 0.0;
float KD = 0.8;

int MAX_THROTTLE = 1400;

float ACC_1G_VALUE = 512.0;

// ============================================================
// 2. GLOBALE VARIABLEN
// ============================================================
WebServer server(80);
bool isRunning = false;

// Zustände: 0=Aus, 1=Takeoff(Zeit), 2=Hover, 3=Takeoff(Acc), -1=Failsafe, -2=Crash
int drone_state = 0;
unsigned long takeoff_start_time = 0;
unsigned long last_heartbeat = 0;

float algo_strength = 1.0;
float smoothing_factor = 0.0;
int hover_throttle = 1050;
int takeoff_throttle = 1150;
int takeoff_time_ms = 300;

float currentRoll = 0.0;
float currentPitch = 0.0;
int16_t currentAccZ = 0;

float estimated_vel_m_s = 0.0;
float estimated_height_m = 0.0;

// Geändert: Startwerte sind 0 (Aus)
int current_m1 = 0, current_m2 = 0, current_m3 = 0, current_m4 = 0;
float last_m1 = 0.0, last_m2 = 0.0, last_m3 = 0.0, last_m4 = 0.0;

float pid_roll_integral = 0, pid_roll_last_error = 0;
float pid_pitch_integral = 0, pid_pitch_last_error = 0;
unsigned long last_pid_time = 0;

HardwareSerial FCSerial(1);

// ============================================================
// 3. MSP PROTOKOLL
// ============================================================
void sendMSP(uint8_t cmd, uint8_t *data, uint8_t n_bytes) {
  uint8_t checksum = 0;
  FCSerial.write('$'); FCSerial.write('M'); FCSerial.write('<');
  FCSerial.write(n_bytes); checksum ^= n_bytes;
  FCSerial.write(cmd); checksum ^= cmd;
  for (int i = 0; i < n_bytes; i++) {
    FCSerial.write(data[i]);
    checksum ^= data[i];
  }
  FCSerial.write(checksum);
}

void setMotors(int m1, int m2, int m3, int m4) {
  // GEÄNDERT: Wenn Wert unter 1000, sende hart 0 (Betaflight Motor AUS)
  m1 = (m1 < 1000) ? 0 : constrain(m1, 1000, MAX_THROTTLE);
  m2 = (m2 < 1000) ? 0 : constrain(m2, 1000, MAX_THROTTLE);
  m3 = (m3 < 1000) ? 0 : constrain(m3, 1000, MAX_THROTTLE);
  m4 = (m4 < 1000) ? 0 : constrain(m4, 1000, MAX_THROTTLE);

  current_m1 = m1;
  current_m2 = m2;
  current_m3 = m3;
  current_m4 = m4;

  uint16_t motors[8] = {
    (uint16_t)m1, (uint16_t)m2,
    (uint16_t)m3, (uint16_t)m4,
    0, 0, 0, 0 // Leere Kanäle auch auf 0 setzen
  };
  sendMSP(214, (uint8_t*)motors, 16);
}

void readMSPResponse() {
  while (FCSerial.available() >= 6) {
    if (FCSerial.read() == '$' && FCSerial.read() == 'M' && FCSerial.read() == '>') {
      uint8_t size = FCSerial.read();
      uint8_t cmd  = FCSerial.read();

      if (cmd == 108 && size == 6) {
        int16_t roll, pitch, yaw;
        FCSerial.readBytes((char*)&roll,  2);
        FCSerial.readBytes((char*)&pitch, 2);
        FCSerial.readBytes((char*)&yaw,   2);
        FCSerial.read();
        currentRoll  = roll  / 10.0;
        currentPitch = pitch / 10.0;
      }
      else if (cmd == 102 && size == 18) {
        int16_t accX, accY, accZ;
        FCSerial.readBytes((char*)&accX, 2);
        FCSerial.readBytes((char*)&accY, 2);
        FCSerial.readBytes((char*)&accZ, 2);
        uint8_t dump[13];
        FCSerial.readBytes((char*)dump, 13);
        currentAccZ = accZ;
      }
      else {
        for (int i=0; i<=size; i++) FCSerial.read();
      }
    }
  }
}

// ============================================================
// 4. PID
// ============================================================
float calculatePID(float target, float current, float &integral, float &last_error, float dt) {
  float error = target - current;
  integral += error * dt;
  integral = constrain(integral, -50, 50);
  float derivative = (error - last_error) / dt;
  last_error = error;
  return (KP * error) + (KI * integral) + (KD * derivative);
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
est. Höhe (Acc): <strong style="color:#00ffcc"><span id='height'>0.00</span> cm</strong>
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

setInterval(() => {
  fetch('/heartbeat').catch(()=>{});
}, 500);

setInterval(() => {
  fetch('/data')
  .then(r=>r.json())
  .then(d=>{
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
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) { delay(500); attempts++; }
  return (WiFi.status() == WL_CONNECTED);
}

void setup() {
  Serial.begin(115200);
  FCSerial.begin(FC_BAUD, SERIAL_8N1, FC_RX_PIN, FC_TX_PIN);

  while (!connectWiFi()) delay(5000);

  ArduinoOTA.setHostname("ESP32-Drohne");
  ArduinoOTA.setPassword("admin123");
  ArduinoOTA.onStart([]() { isRunning=false; drone_state=0; setMotors(0, 0, 0, 0); });
  ArduinoOTA.begin();

  server.on("/", []() { server.send(200, "text/html", htmlDashboard); });
  server.on("/heartbeat", []() { last_heartbeat = millis(); server.send(200); });

  server.on("/start_time", []() {
    if (abs(currentRoll) > 5.0 || abs(currentPitch) > 5.0) { server.send(400, "text/plain", "Drohne nicht flach!"); return; }
    isRunning = true;
    drone_state = 1;
    takeoff_start_time = millis();
    last_heartbeat = millis();
    pid_roll_integral = 0; pid_pitch_integral = 0;
    last_pid_time = micros();
    // Beim Starten weich von 1000 anfangen (Smoothing)
    last_m1 = 1000; last_m2 = 1000; last_m3 = 1000; last_m4 = 1000;
    server.send(200);
  });

  server.on("/start_acc", []() {
    if (abs(currentRoll) > 5.0 || abs(currentPitch) > 5.0) { server.send(400, "text/plain", "Drohne nicht flach!"); return; }
    isRunning = true;
    drone_state = 3;
    takeoff_start_time = millis();
    last_heartbeat = millis();

    estimated_vel_m_s = 0.0; estimated_height_m = 0.0;
    pid_roll_integral = 0; pid_pitch_integral = 0;
    last_pid_time = micros();

    last_m1 = 1000; last_m2 = 1000; last_m3 = 1000; last_m4 = 1000;
    server.send(200);
  });

  server.on("/stop", []() {
    isRunning = false; drone_state = 0;
    estimated_vel_m_s = 0; estimated_height_m = 0;
    // GEÄNDERT: Schicke 0!
    setMotors(0, 0, 0, 0);
    last_m1 = 0; last_m2 = 0; last_m3 = 0; last_m4 = 0;
    server.send(200);
  });

  server.on("/set_hover", []() { hover_throttle = server.arg("val").toInt(); server.send(200); });
  server.on("/set_takeoff_thr", []() { takeoff_throttle = server.arg("val").toInt(); server.send(200); });
  server.on("/set_takeoff_time", []() { takeoff_time_ms = server.arg("val").toInt(); server.send(200); });

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

  static unsigned long last_msp_req = 0;
  if (millis() - last_msp_req > 20) {
    sendMSP(108, NULL, 0);
    sendMSP(102, NULL, 0);
    last_msp_req = millis();
  }
  readMSPResponse();

  if (isRunning && (millis() - last_heartbeat > 1500)) {
    isRunning = false; drone_state = -1;
    setMotors(0, 0, 0, 0);
  }

  if (isRunning && (abs(currentRoll) > 60.0 || abs(currentPitch) > 60.0)) {
    isRunning = false; drone_state = -2;
    setMotors(0, 0, 0, 0);
  }

  if (isRunning) {
    unsigned long now = micros();
    float dt = (now - last_pid_time) / 1000000.0;
    if (dt <= 0 || dt > 0.1) dt = 0.001;
    last_pid_time = now;

    float rC = calculatePID(0.0, currentRoll,  pid_roll_integral,  pid_roll_last_error,  dt) * algo_strength;
    float pC = calculatePID(0.0, currentPitch, pid_pitch_integral, pid_pitch_last_error, dt) * algo_strength;

    int current_base_throttle = 1000;

    if (drone_state == 1) {
      current_base_throttle = takeoff_throttle;
      if (millis() - takeoff_start_time >= takeoff_time_ms) drone_state = 2;
    }
    else if (drone_state == 3) {
      current_base_throttle = takeoff_throttle;
      float linear_accel_m_s2 = (currentAccZ / ACC_1G_VALUE) * 9.81 - 9.81;
      if (abs(linear_accel_m_s2) < 0.1) linear_accel_m_s2 = 0.0;

      estimated_vel_m_s += linear_accel_m_s2 * dt;
      estimated_height_m += estimated_vel_m_s * dt;

      if (estimated_height_m >= 0.18 || (millis() - takeoff_start_time >= 2000)) {
        drone_state = 2;
      }
    }
    else if (drone_state == 2) {
      current_base_throttle = hover_throttle;
    }

    float target_m1 = current_base_throttle - rC + pC;
    float target_m2 = current_base_throttle - rC - pC;
    float target_m3 = current_base_throttle + rC + pC;
    float target_m4 = current_base_throttle + rC - pC;

    last_m1 = (target_m1 * (1.0 - smoothing_factor)) + (last_m1 * smoothing_factor);
    last_m2 = (target_m2 * (1.0 - smoothing_factor)) + (last_m2 * smoothing_factor);
    last_m3 = (target_m3 * (1.0 - smoothing_factor)) + (last_m3 * smoothing_factor);
    last_m4 = (target_m4 * (1.0 - smoothing_factor)) + (last_m4 * smoothing_factor);

    setMotors(last_m1, last_m2, last_m3, last_m4);

    delay(5);

  } else {
    // GEÄNDERT: Schicke 0 anstatt 1000, und das im schnelleren Intervall (200ms)
    static unsigned long lastStop = 0;
    if (millis() - lastStop > 200) {
      setMotors(0, 0, 0, 0);
      lastStop = millis();
    }
  }
}