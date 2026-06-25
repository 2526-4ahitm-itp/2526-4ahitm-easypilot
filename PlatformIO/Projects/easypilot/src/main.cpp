#include <WiFi.h>
#include <WebServer.h>
#include <esp_wifi.h>
#include <ArduinoOTA.h>

// ============================================================
// 1. EINSTELLUNGEN
// ============================================================
const char* ssid     = "Dav";
const char* password = "12345678";

#define FC_TX_PIN 21
#define FC_RX_PIN 20
#define FC_BAUD   115200

float KP = 1.5;
float KI = 0.3;
float KD = 0.8;

int   MAX_THROTTLE  = 1400;
float ACC_1G_VALUE  = 512.0;

const float ACC_DEADBAND_M_S2            = 0.3;
const float VEL_DECAY                    = 0.98;
const unsigned long ACC_NO_CHANGE_TIMEOUT_MS = 500;
const float         ACC_MIN_HEIGHT_CHANGE_M  = 0.005;
const unsigned long CONTROL_INTERVAL_MS      = 5;

// ============================================================
// 2. GLOBALE VARIABLEN
// ============================================================
WebServer server(80);
bool isRunning = false;

int drone_state = 0;

unsigned long takeoff_start_time      = 0;
unsigned long last_heartbeat          = 0;
unsigned long last_control_time_ms    = 0;
unsigned long last_wifi_attempt       = 0;  // WiFi reconnect cooldown

float algo_strength    = 1.0;
float smoothing_factor = 0.0;
int   hover_throttle   = 1050;
int   takeoff_throttle = 1150;
int   takeoff_time_ms  = 300;

float   currentRoll  = 0.0;
float   currentPitch = 0.0;
int16_t currentAccZ  = 0;

float estimated_vel_m_s          = 0.0;
float estimated_height_m         = 0.0;
float last_height_check_m        = 0.0;
unsigned long last_height_change_time = 0;

int   current_m1 = 1000, current_m2 = 1000, current_m3 = 1000, current_m4 = 1000;
float last_m1    = 1000.0, last_m2  = 1000.0, last_m3  = 1000.0, last_m4  = 1000.0;

float pid_roll_integral   = 0, pid_roll_last_error   = 0;
float pid_pitch_integral  = 0, pid_pitch_last_error  = 0;
unsigned long last_pid_time = 0;

HardwareSerial FCSerial(1);

// ============================================================
// 3. WIFI
// ============================================================
bool connectWiFi() {
  Serial.println("Verbinde mit WiFi...");
  WiFi.mode(WIFI_STA);
  WiFi.setTxPower(WIFI_POWER_8_5dBm);
  esp_wifi_set_protocol(WIFI_IF_STA, WIFI_PROTOCOL_11B | WIFI_PROTOCOL_11G | WIFI_PROTOCOL_11N);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("\nVerbunden! IP: ");
    Serial.println(WiFi.localIP());
    return true;
  }
  Serial.println("\nVerbindung fehlgeschlagen.");
  return false;
}

// ============================================================
// 4. MSP PROTOKOLL
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

// Quadrotor-X Geometrie (Vogelperspektive):
//
//   M4 (CCW) ---[FRONT]--- M2 (CW)
//      |                    |
//   M3 (CW)  ---[BACK]---- M1 (CCW)
//
// Roll+  → M1/M2 schneller, M3/M4 langsamer
// Pitch+ → M1/M3 schneller, M2/M4 langsamer
void setMotors(int m1, int m2, int m3, int m4) {
  m1 = constrain(m1, 1000, MAX_THROTTLE);
  m2 = constrain(m2, 1000, MAX_THROTTLE);
  m3 = constrain(m3, 1000, MAX_THROTTLE);
  m4 = constrain(m4, 1000, MAX_THROTTLE);
  current_m1 = m1; current_m2 = m2;
  current_m3 = m3; current_m4 = m4;

  uint16_t motors[8] = {
    (uint16_t)m1, (uint16_t)m2,
    (uint16_t)m3, (uint16_t)m4,
    1000, 1000, 1000, 1000
  };
  sendMSP(214, (uint8_t*)motors, 16);
}

void stopMotors() {
  setMotors(1000, 1000, 1000, 1000);
  last_m1 = last_m2 = last_m3 = last_m4 = 1000;
}

void readMSPResponse() {
  while (FCSerial.available() >= 6) {
    if (FCSerial.read() != '$') continue;
    if (FCSerial.read() != 'M') continue;
    if (FCSerial.read() != '>') continue;

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
      for (int i = 0; i <= size; i++) FCSerial.read();
    }
  }
}

// ============================================================
// 5. PID — mit Anti-Windup
// ============================================================
float calculatePID(float target, float current,
                   float &integral, float &last_error, float dt) {
  float error = target - current;
  if (abs(error) < 45.0) {
    integral += error * dt;
  }
  integral = constrain(integral, -30.0, 30.0);
  float derivative = (error - last_error) / dt;
  last_error = error;
  return (KP * error) + (KI * integral) + (KD * derivative);
}

// ============================================================
// 6. ZUSTAND ZURÜCKSETZEN
// ============================================================
void resetFlightState() {
  isRunning           = false;
  drone_state         = 0;
  estimated_vel_m_s   = 0.0;
  estimated_height_m  = 0.0;
  last_height_check_m = 0.0;
  pid_roll_integral   = 0; pid_roll_last_error  = 0;
  pid_pitch_integral  = 0; pid_pitch_last_error = 0;
  stopMotors();
}

// ============================================================
// 7. DASHBOARD HTML
// ============================================================
const char* htmlDashboard = R"rawliteral(
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FC Dashboard v2</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Barlow:wght@400;600;700&display=swap');
  :root {
    --bg:      #0d0f14;
    --surface: #151820;
    --border:  #252a35;
    --accent:  #00e5a0;
    --warn:    #ffaa00;
    --danger:  #ff3b5c;
    --info:    #3b9eff;
    --text:    #c8cdd8;
    --muted:   #5a6070;
    --mono:    'Share Tech Mono', monospace;
    --sans:    'Barlow', sans-serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: var(--sans); min-height: 100vh; }

  header {
    border-bottom: 1px solid var(--border);
    padding: 14px 20px;
    display: flex; align-items: center; gap: 12px;
    background: var(--surface);
  }
  .logo { width: 10px; height: 10px; background: var(--accent); border-radius: 50%;
          box-shadow: 0 0 8px var(--accent); animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
  header h1 { font-size: 13px; letter-spacing: 3px; text-transform: uppercase;
              font-weight: 600; color: var(--accent); }
  header .ver { margin-left: auto; font-family: var(--mono); font-size: 11px; color: var(--muted); }

  .layout { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: var(--border); }
  @media(max-width:700px){ .layout { grid-template-columns: 1fr; } }
  .panel { background: var(--bg); padding: 18px; }
  .panel-title { font-size: 10px; letter-spacing: 2px; text-transform: uppercase;
                 color: var(--muted); margin-bottom: 14px; }

  .status-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }
  .badge {
    font-family: var(--mono); font-size: 11px; padding: 3px 10px;
    border-radius: 3px; border: 1px solid; text-transform: uppercase; letter-spacing: 1px;
  }
  .badge.active  { color: var(--accent); border-color: var(--accent); background: rgba(0,229,160,.08); }
  .badge.stopped { color: var(--muted);  border-color: var(--muted);  background: transparent; }
  .badge.fail    { color: var(--danger); border-color: var(--danger); background: rgba(255,59,92,.1);
                   animation: pulse .6s infinite; }
  .badge.warn    { color: var(--warn);   border-color: var(--warn);   background: rgba(255,170,0,.08); }

  .tele-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .tele-item { background: var(--surface); border: 1px solid var(--border);
               border-radius: 4px; padding: 10px 12px; }
  .tele-label { font-size: 10px; color: var(--muted); letter-spacing: 1px;
                text-transform: uppercase; margin-bottom: 4px; }
  .tele-val   { font-family: var(--mono); font-size: 22px; font-weight: 700; color: var(--text); }
  .tele-val.accent { color: var(--accent); }
  .tele-val.warn   { color: var(--warn); }
  .tele-unit  { font-size: 11px; color: var(--muted); margin-left: 3px; }

  .motor-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .motor-card { background: var(--surface); border: 1px solid var(--border);
                border-radius: 4px; padding: 10px; }
  .motor-label { font-size: 10px; color: var(--muted); letter-spacing: 1px; margin-bottom: 6px; }
  .motor-val   { font-family: var(--mono); font-size: 18px; color: var(--info); }
  .motor-bar   { height: 3px; background: var(--border); border-radius: 2px; margin-top: 6px; }
  .motor-fill  { height: 100%; background: var(--info); border-radius: 2px; transition: width .15s; }

  .btn-row { display: flex; flex-direction: column; gap: 8px; }
  .btn {
    font-family: var(--sans); font-size: 13px; font-weight: 700;
    letter-spacing: 2px; text-transform: uppercase;
    padding: 14px; border: 1px solid; border-radius: 4px;
    background: transparent; cursor: pointer; transition: all .15s; width: 100%;
  }
  .btn:active { transform: scale(.98); }
  .btn-start { color: var(--accent); border-color: var(--accent); }
  .btn-start:hover { background: rgba(0,229,160,.1); }
  .btn-acc   { color: var(--info);   border-color: var(--info); }
  .btn-acc:hover   { background: rgba(59,158,255,.1); }
  .btn-stop  { color: var(--danger); border-color: var(--danger); }
  .btn-stop:hover  { background: rgba(255,59,92,.1); }

  .param-row { margin-bottom: 14px; }
  .param-row label {
    font-size: 11px; color: var(--muted); letter-spacing: 1px; text-transform: uppercase;
    display: flex; justify-content: space-between; margin-bottom: 6px;
  }
  .param-row label span { color: var(--text); font-family: var(--mono); }
  input[type=range] {
    -webkit-appearance: none; width: 100%; height: 2px;
    background: var(--border); border-radius: 2px; outline: none;
  }
  input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none; width: 14px; height: 14px;
    background: var(--accent); border-radius: 50%; cursor: pointer;
  }

  canvas { width: 100%; display: block; background: var(--surface);
           border-radius: 4px; border: 1px solid var(--border); }

  .alert-banner {
    display: none; background: rgba(255,59,92,.12); border: 1px solid var(--danger);
    border-radius: 4px; padding: 10px 14px; font-size: 12px;
    color: var(--danger); letter-spacing: 1px; text-align: center;
    text-transform: uppercase; margin-top: 10px;
  }
  .alert-banner.show { display: block; }
  .divider { border: none; border-top: 1px solid var(--border); margin: 14px 0; }
</style>
</head>
<body>

<header>
  <div class="logo"></div>
  <h1>FC Dashboard v2</h1>
  <span class="ver">ESP32 · Diplomarbeit</span>
</header>

<div class="layout">

  <div class="panel">
    <div class="panel-title">Status</div>
    <div class="status-row">
      <span class="badge stopped" id="badge-run">GESTOPPT</span>
      <span class="badge stopped" id="badge-phase">IDLE</span>
    </div>
    <div id="alert-box" class="alert-banner"></div>
    <hr class="divider">
    <div class="panel-title">Telemetrie</div>
    <div class="tele-grid">
      <div class="tele-item">
        <div class="tele-label">Roll</div>
        <div class="tele-val" id="t-roll">0.0<span class="tele-unit">°</span></div>
      </div>
      <div class="tele-item">
        <div class="tele-label">Pitch</div>
        <div class="tele-val" id="t-pitch">0.0<span class="tele-unit">°</span></div>
      </div>
      <div class="tele-item">
        <div class="tele-label">Höhe (est.)</div>
        <div class="tele-val accent" id="t-height">0.00<span class="tele-unit">cm</span></div>
      </div>
      <div class="tele-item">
        <div class="tele-label">Ø Motor</div>
        <div class="tele-val warn" id="t-avg">1000</div>
      </div>
    </div>
  </div>

  <div class="panel">
    <div class="panel-title">Motoren (Max 1400)</div>
    <div class="motor-grid">
      <div class="motor-card">
        <div class="motor-label">M4 · VL (CCW)</div>
        <div class="motor-val" id="m4">1000</div>
        <div class="motor-bar"><div class="motor-fill" id="m4b" style="width:0%"></div></div>
      </div>
      <div class="motor-card">
        <div class="motor-label">M2 · VR (CW)</div>
        <div class="motor-val" id="m2">1000</div>
        <div class="motor-bar"><div class="motor-fill" id="m2b" style="width:0%"></div></div>
      </div>
      <div class="motor-card">
        <div class="motor-label">M3 · HL (CW)</div>
        <div class="motor-val" id="m3">1000</div>
        <div class="motor-bar"><div class="motor-fill" id="m3b" style="width:0%"></div></div>
      </div>
      <div class="motor-card">
        <div class="motor-label">M1 · HR (CCW)</div>
        <div class="motor-val" id="m1">1000</div>
        <div class="motor-bar"><div class="motor-fill" id="m1b" style="width:0%"></div></div>
      </div>
    </div>
  </div>

  <div class="panel">
    <div class="panel-title">Parameter</div>
    <div class="param-row">
      <label>Schwebegas (Hover) <span id="lhv">1050</span></label>
      <input type="range" min="1050" max="1400" value="1050"
        oninput='fetch("/set_hover?val="+this.value);document.getElementById("lhv").textContent=this.value'>
    </div>
    <div class="param-row">
      <label>Takeoff-Gas <span id="ltv">1150</span></label>
      <input type="range" min="1050" max="1400" value="1150"
        oninput='fetch("/set_takeoff_thr?val="+this.value);document.getElementById("ltv").textContent=this.value'>
    </div>
    <div class="param-row">
      <label>Takeoff-Dauer (Zeit-Modus) <span id="ltt">300</span> ms</label>
      <input type="range" min="0" max="1000" value="300"
        oninput='fetch("/set_takeoff_time?val="+this.value);document.getElementById("ltt").textContent=this.value'>
    </div>
    <hr class="divider">
    <div class="btn-row">
      <button class="btn btn-start" onclick="doStart('/start_time')">▶ Start · Zeitbasiert</button>
      <button class="btn btn-acc"   onclick="doStart('/start_acc')">▶ Start · Accelerometer (18 cm)</button>
      <button class="btn btn-stop"  onclick="doStop()">■ NOT-AUS / RESET</button>
    </div>
  </div>

  <div class="panel">
    <div class="panel-title">Höhenverlauf (Acc-Integration)</div>
    <canvas id="hchart" height="160"></canvas>
  </div>

</div>

<script>
const MAX_POINTS = 80;
const hData = new Array(MAX_POINTS).fill(0);
const canvas = document.getElementById('hchart');
const ctx    = canvas.getContext('2d');

function drawChart() {
  const W = canvas.offsetWidth * devicePixelRatio;
  const H = canvas.offsetHeight * devicePixelRatio;
  canvas.width = W; canvas.height = H;
  const pad = { t:10*devicePixelRatio, b:20*devicePixelRatio,
                l:36*devicePixelRatio, r:10*devicePixelRatio };
  const cw = W - pad.l - pad.r;
  const ch = H - pad.t - pad.b;
  ctx.clearRect(0, 0, W, H);
  const maxH = Math.max(...hData, 0.20);
  const step = cw / (MAX_POINTS - 1);

  ctx.strokeStyle = '#252a35'; ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = pad.t + ch - (i/4)*ch;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(pad.l+cw, y); ctx.stroke();
    ctx.fillStyle = '#5a6070';
    ctx.font = `${10*devicePixelRatio}px 'Share Tech Mono', monospace`;
    ctx.textAlign = 'right';
    ctx.fillText((maxH*i/4*100).toFixed(0)+' cm', pad.l-4, y+4);
  }

  ctx.beginPath();
  hData.forEach((v, i) => {
    const x = pad.l + i*step;
    const y = pad.t + ch - (v/maxH)*ch;
    i === 0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
  });
  ctx.strokeStyle = '#00e5a0'; ctx.lineWidth = 1.5*devicePixelRatio; ctx.stroke();

  ctx.lineTo(pad.l+(MAX_POINTS-1)*step, pad.t+ch);
  ctx.lineTo(pad.l, pad.t+ch); ctx.closePath();
  const grad = ctx.createLinearGradient(0, pad.t, 0, pad.t+ch);
  grad.addColorStop(0, 'rgba(0,229,160,.18)');
  grad.addColorStop(1, 'rgba(0,229,160,.01)');
  ctx.fillStyle = grad; ctx.fill();
}

function motorPct(val) {
  return Math.max(0, Math.min(100, ((val-1000)/400)*100)).toFixed(1)+'%';
}
function setAlert(msg) {
  const el = document.getElementById('alert-box');
  el.textContent = msg; el.className = 'alert-banner show';
}
function clearAlert() { document.getElementById('alert-box').className = 'alert-banner'; }

async function doStart(ep) {
  clearAlert();
  const r = await fetch(ep);
  if (!r.ok) { const msg = await r.text(); setAlert('START ABGEBROCHEN: ' + msg); }
}
function doStop() { clearAlert(); fetch('/stop'); }

setInterval(() => fetch('/heartbeat').catch(()=>{}), 500);

setInterval(() => {
  fetch('/data').then(r => r.json()).then(d => {
    const runBadge = document.getElementById('badge-run');
    if      (d.state === -1) { runBadge.textContent='VERBINDUNG LOST'; runBadge.className='badge fail'; }
    else if (d.state === -2) { runBadge.textContent='CRASH DETECTED';  runBadge.className='badge fail'; }
    else if (d.running)      { runBadge.textContent='AKTIV';           runBadge.className='badge active'; }
    else                     { runBadge.textContent='GESTOPPT';        runBadge.className='badge stopped'; }

    const phases = {0:'IDLE',1:'TAKEOFF · ZEIT',2:'HOVER',3:'TAKEOFF · ACC','-1':'FAILSAFE','-2':'CRASH'};
    const pBadge = document.getElementById('badge-phase');
    pBadge.textContent = phases[d.state] ?? 'UNKNOWN';
    pBadge.className = d.state===2 ? 'badge active' : d.state<0 ? 'badge fail' :
                       d.state>0   ? 'badge warn'   : 'badge stopped';

    document.getElementById('t-roll').innerHTML   = d.roll.toFixed(1)+'<span class="tele-unit">°</span>';
    document.getElementById('t-pitch').innerHTML  = d.pitch.toFixed(1)+'<span class="tele-unit">°</span>';
    document.getElementById('t-height').innerHTML = (d.height*100).toFixed(2)+'<span class="tele-unit">cm</span>';
    document.getElementById('t-avg').textContent  = Math.round((d.m1+d.m2+d.m3+d.m4)/4);

    ['m1','m2','m3','m4'].forEach(k => {
      document.getElementById(k).textContent     = d[k];
      document.getElementById(k+'b').style.width = motorPct(d[k]);
    });

    hData.push(d.height);
    if (hData.length > MAX_POINTS) hData.shift();
    drawChart();
  }).catch(()=>{});
}, 150);

drawChart();
window.addEventListener('resize', drawChart);
</script>
</body>
</html>
)rawliteral";

// ============================================================
// 8. SETUP
// ============================================================
void setup() {
  Serial.begin(115200);
  FCSerial.begin(FC_BAUD, SERIAL_8N1, FC_RX_PIN, FC_TX_PIN);

  // Single connect attempt on boot — no hammering loop
  connectWiFi();

  ArduinoOTA.setHostname("ESP32-Drohne");
  ArduinoOTA.setPassword("admin123");
  ArduinoOTA.onStart([]() { resetFlightState(); });
  ArduinoOTA.begin();

  server.on("/", []() { server.send(200, "text/html", htmlDashboard); });

  server.on("/heartbeat", []() {
    last_heartbeat = millis();
    server.send(200);
  });

  server.on("/start_time", []() {
    if (abs(currentRoll) > 5.0 || abs(currentPitch) > 5.0) {
      server.send(400, "text/plain", "Drohne nicht flach! Roll=" +
        String(currentRoll,1) + " Pitch=" + String(currentPitch,1));
      return;
    }
    isRunning = true; drone_state = 1;
    takeoff_start_time = last_heartbeat = millis();
    pid_roll_integral = pid_pitch_integral = 0;
    pid_roll_last_error = pid_pitch_last_error = 0;
    last_pid_time = micros();
    last_m1 = last_m2 = last_m3 = last_m4 = 1000;
    server.send(200);
  });

  server.on("/start_acc", []() {
    if (abs(currentRoll) > 5.0 || abs(currentPitch) > 5.0) {
      server.send(400, "text/plain", "Drohne nicht flach! Roll=" +
        String(currentRoll,1) + " Pitch=" + String(currentPitch,1));
      return;
    }
    isRunning = true; drone_state = 3;
    takeoff_start_time = last_heartbeat = millis();
    estimated_vel_m_s = estimated_height_m = last_height_check_m = 0.0;
    last_height_change_time = millis();
    pid_roll_integral = pid_pitch_integral = 0;
    pid_roll_last_error = pid_pitch_last_error = 0;
    last_pid_time = micros();
    last_m1 = last_m2 = last_m3 = last_m4 = 1000;
    server.send(200);
  });

  server.on("/stop", []() { resetFlightState(); server.send(200); });

  server.on("/set_hover",        []() { hover_throttle   = server.arg("val").toInt(); server.send(200); });
  server.on("/set_takeoff_thr",  []() { takeoff_throttle = server.arg("val").toInt(); server.send(200); });
  server.on("/set_takeoff_time", []() { takeoff_time_ms  = server.arg("val").toInt(); server.send(200); });

  server.on("/data", []() {
    String j = "{";
    j += "\"running\":"  + String(isRunning ? "true" : "false") + ",";
    j += "\"state\":"    + String(drone_state)           + ",";
    j += "\"roll\":"     + String(currentRoll,  2)       + ",";
    j += "\"pitch\":"    + String(currentPitch, 2)       + ",";
    j += "\"height\":"   + String(estimated_height_m, 4) + ",";
    j += "\"m1\":"       + String(current_m1)            + ",";
    j += "\"m2\":"       + String(current_m2)            + ",";
    j += "\"m3\":"       + String(current_m3)            + ",";
    j += "\"m4\":"       + String(current_m4);
    j += "}";
    server.send(200, "application/json", j);
  });

  server.begin();
  Serial.println("Webserver gestartet");
}

// ============================================================
// 9. HAUPTLOOP — nicht-blockierend, kein delay()
// ============================================================
void loop() {
  server.handleClient();
  ArduinoOTA.handle();

  // WiFi reconnect mit 10s Cooldown — kein AP-Spamming
  if (WiFi.status() != WL_CONNECTED) {
    if (millis() - last_wifi_attempt > 10000) {
      last_wifi_attempt = millis();
      connectWiFi();
    }
  }

  // Sensordaten alle 20ms
  static unsigned long last_msp_req = 0;
  if (millis() - last_msp_req >= 20) {
    sendMSP(108, NULL, 0);
    sendMSP(102, NULL, 0);
    last_msp_req = millis();
  }
  readMSPResponse();

  // Heartbeat-Watchdog
  if (isRunning && (millis() - last_heartbeat > 1500)) {
    isRunning = false; drone_state = -1;
    stopMotors();
    return;
  }

  // Crash-Erkennung
  if (isRunning && (abs(currentRoll) > 60.0 || abs(currentPitch) > 60.0)) {
    isRunning = false; drone_state = -2;
    stopMotors();
    return;
  }

  if (isRunning) {
    unsigned long now_ms = millis();
    if (now_ms - last_control_time_ms < CONTROL_INTERVAL_MS) return;
    last_control_time_ms = now_ms;

    unsigned long now_us = micros();
    float dt = (now_us - last_pid_time) / 1000000.0;
    if (dt <= 0 || dt > 0.1) dt = 0.005;
    last_pid_time = now_us;

    float rC = calculatePID(0.0, currentRoll,  pid_roll_integral,  pid_roll_last_error,  dt) * algo_strength;
    float pC = calculatePID(0.0, currentPitch, pid_pitch_integral, pid_pitch_last_error, dt) * algo_strength;

    int base = 1000;

    // TAKEOFF: ZEITBASIERT
    if (drone_state == 1) {
      base = takeoff_throttle;
      if (millis() - takeoff_start_time >= (unsigned long)takeoff_time_ms)
        drone_state = 2;
    }
    // TAKEOFF: ACCELEROMETER
    else if (drone_state == 3) {
      base = takeoff_throttle;

      float accel = ((float)currentAccZ / ACC_1G_VALUE) * 9.81f - 9.81f;
      if (fabsf(accel) < ACC_DEADBAND_M_S2) accel = 0.0f;

      estimated_vel_m_s   = estimated_vel_m_s * VEL_DECAY + accel * dt;
      estimated_height_m += estimated_vel_m_s * dt;

      if (estimated_height_m < 0.0f) {
        estimated_height_m = 0.0f;
        estimated_vel_m_s  = 0.0f;
      }

      if (fabsf(estimated_height_m - last_height_check_m) >= ACC_MIN_HEIGHT_CHANGE_M) {
        last_height_check_m     = estimated_height_m;
        last_height_change_time = millis();
      }
      bool noChange = (millis() - last_height_change_time > ACC_NO_CHANGE_TIMEOUT_MS);

      if (estimated_height_m >= 0.18f || noChange ||
          millis() - takeoff_start_time >= 2000)
        drone_state = 2;
    }
    // HOVER
    else if (drone_state == 2) {
      base = hover_throttle;
    }

    // Motorenmischung Quadrotor-X
    float t1 = base - rC + pC;
    float t2 = base - rC - pC;
    float t3 = base + rC + pC;
    float t4 = base + rC - pC;

    last_m1 = t1*(1.0-smoothing_factor) + last_m1*smoothing_factor;
    last_m2 = t2*(1.0-smoothing_factor) + last_m2*smoothing_factor;
    last_m3 = t3*(1.0-smoothing_factor) + last_m3*smoothing_factor;
    last_m4 = t4*(1.0-smoothing_factor) + last_m4*smoothing_factor;

    setMotors((int)last_m1, (int)last_m2, (int)last_m3, (int)last_m4);

  } else {
    // GESTOPPT: Motoren sicher auf 1000 halten
    static unsigned long lastStop = 0;
    if (millis() - lastStop >= 500) {
      stopMotors();
      lastStop = millis();
    }
  }
}