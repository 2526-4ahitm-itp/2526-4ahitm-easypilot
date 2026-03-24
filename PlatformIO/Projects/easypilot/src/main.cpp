#include <Arduino.h>     // Zwingend nötig für PlatformIO
#include <WiFi.h>
#include <WebServer.h>

// ============================================================
// 1. EINSTELLUNGEN
// ============================================================
const char* ssid = "Sim";
const char* password = "123456789";

#define FC_TX_PIN 17  
#define FC_RX_PIN 18  
#define FC_BAUD 115200

// PID Parameter
float KP = 1.5;
float KI = 0.0;
float KD = 0.8;

int BASE_THROTTLE = 1050; 
int MAX_THROTTLE = 1800;

// ============================================================
// 2. GLOBALE VARIABLEN
// ============================================================
WebServer server(80);
bool isRunning = false; 
float algo_strength = 1.0; 

float currentRoll = 0.0;
float currentPitch = 0.0;
int current_m1 = 1000, current_m2 = 1000, current_m3 = 1000, current_m4 = 1000;

float pid_roll_integral = 0, pid_roll_last_error = 0;
float pid_pitch_integral = 0, pid_pitch_last_error = 0;
unsigned long last_pid_time = 0;

HardwareSerial FCSerial(1); 

// ============================================================
// 3. MSP PROTOKOLL FUNKTIONEN
// ============================================================
void sendMSP(uint8_t cmd, uint8_t *data, uint8_t n_bytes) {
  uint8_t checksum = 0;
  FCSerial.write('$'); FCSerial.write('M'); FCSerial.write('<');
  FCSerial.write(n_bytes); checksum ^= n_bytes;
  FCSerial.write(cmd); checksum ^= cmd;
  for (int i = 0; i < n_bytes; i++) {
    FCSerial.write(data[i]); checksum ^= data[i];
  }
  FCSerial.write(checksum);
}

void setMotors(int m1, int m2, int m3, int m4) {
  m1 = constrain(m1, 1000, 2000);
  m2 = constrain(m2, 1000, 2000);
  m3 = constrain(m3, 1000, 2000);
  m4 = constrain(m4, 1000, 2000);

  current_m1 = m1; current_m2 = m2; current_m3 = m3; current_m4 = m4;

  uint16_t motors[8] = {(uint16_t)m1, (uint16_t)m2, (uint16_t)m3, (uint16_t)m4, 1000, 1000, 1000, 1000};
  sendMSP(214, (uint8_t*)motors, 16); 
}

void requestAttitude() { sendMSP(108, NULL, 0); }

void readAttitudeResponse() {
  unsigned long start = millis();
  while (FCSerial.available() < 6 && millis() - start < 10) { delay(1); }

  if (FCSerial.available() >= 6) {
    if (FCSerial.read() == '$' && FCSerial.read() == 'M' && FCSerial.read() == '>') {
      uint8_t size = FCSerial.read();
      uint8_t cmd = FCSerial.read();
      if (cmd == 108 && size >= 6) {
        int16_t roll, pitch, yaw;
        FCSerial.readBytes((char*)&roll, 2);
        FCSerial.readBytes((char*)&pitch, 2);
        FCSerial.readBytes((char*)&yaw, 2);
        FCSerial.read(); 
        currentRoll = roll / 10.0;
        currentPitch = pitch / 10.0;
      }
    }
    while(FCSerial.available()) FCSerial.read(); 
  }
}

// ============================================================
// 4. PID LOGIK
// ============================================================
float calculatePID(float target, float current, float &integral, float &last_error) {
  float error = target - current;
  unsigned long now = micros();
  float dt = (now - last_pid_time) / 1000000.0;
  if(dt <= 0) dt = 0.001;

  integral += error * dt;
  integral = constrain(integral, -50, 50);
  float derivative = (error - last_error) / dt;
  last_error = error;
  
  return (KP * error) + (KI * integral) + (KD * derivative);
}

// ============================================================
// 5. WEB-DASHBOARD (HTML & JS)
// ============================================================
const char* htmlDashboard = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <style>
    body { font-family: Arial, sans-serif; text-align: center; margin: 20px; background-color: #222; color: #fff; }
    .box { background: #333; padding: 15px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    button { padding: 15px; font-size: 18px; font-weight: bold; width: 100%; margin-bottom: 10px; border: none; border-radius: 5px; cursor: pointer; color: white; }
    .btn-start { background: #28a745; }
    .btn-stop { background: #dc3545; }
    input[type=range] { width: 100%; margin: 15px 0; }
    .grid { display: grid; grid-template-columns: 50% 50%; gap: 10px; font-size: 20px; }
  </style>
</head>
<body>
  <h2>FC Control Dashboard</h2>
  <div class='box'>
    <p style='font-size: 20px;'>Status: <strong id='status'>VERBINDET...</strong></p>
    <p>Roll: <span id='roll'>0.0</span>&deg; | Pitch: <span id='pitch'>0.0</span>&deg;</p>
  </div>
  <div class='box'>
    <h3>Motoren (PWM)</h3>
    <div class='grid'>
      <div>M4 (VL): <span id='m4'>1000</span></div><div>M2 (VR): <span id='m2'>1000</span></div>
      <div>M3 (HL): <span id='m3'>1000</span></div><div>M1 (HR): <span id='m1'>1000</span></div>
    </div>
  </div>
  <div class='box'>
    <h3>Regler-Stärke: <span id='gain_val'>100</span>%</h3>
    <input type='range' min='0' max='200' value='100' oninput='updateGain(this.value)'>
  </div>
  <button class='btn-start' onclick='fetch("/start")'>START BALANCE</button>
  <button class='btn-stop' onclick='fetch("/stop")'>NOT-AUS / STOP</button>
  <script>
    function updateGain(val) {
      document.getElementById('gain_val').innerText = val;
      fetch('/set_gain?val=' + val);
    }
    setInterval(() => {
      fetch('/data').then(r => r.json()).then(data => {
        let statEl = document.getElementById('status');
        statEl.innerText = data.running ? "AKTIV" : "GESTOPPT";
        statEl.style.color = data.running ? "#28a745" : "#dc3545";
        document.getElementById('roll').innerText = data.roll.toFixed(1);
        document.getElementById('pitch').innerText = data.pitch.toFixed(1);
        document.getElementById('m1').innerText = data.m1;
        document.getElementById('m2').innerText = data.m2;
        document.getElementById('m3').innerText = data.m3;
        document.getElementById('m4').innerText = data.m4;
      });
    }, 500); 
  </script>
</body>
</html>
)rawliteral";

// ============================================================
// 6. SETUP
// ============================================================
void setup() {
  Serial.begin(115200); 
  FCSerial.begin(FC_BAUD, SERIAL_8N1, FC_RX_PIN, FC_TX_PIN); 

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\nWLAN Verbunden: " + WiFi.localIP().toString());

  server.on("/", []() { server.send(200, "text/html", htmlDashboard); });
  
  server.on("/start", []() {
    isRunning = true;
    pid_roll_integral = 0; pid_pitch_integral = 0;
    last_pid_time = micros();
    server.send(200, "text/plain", "OK");
  });

  server.on("/stop", []() {
    isRunning = false;
    setMotors(1000, 1000, 1000, 1000); 
    server.send(200, "text/plain", "OK");
  });

  server.on("/set_gain", []() {
    if (server.hasArg("val")) algo_strength = server.arg("val").toFloat() / 100.0; 
    server.send(200, "text/plain", "OK");
  });

  server.on("/data", []() {
    String json = "{";
    json += "\"running\":" + String(isRunning ? "true" : "false") + ",";
    json += "\"roll\":" + String(currentRoll) + ",";
    json += "\"pitch\":" + String(currentPitch) + ",";
    json += "\"m1\":" + String(current_m1) + ",";
    json += "\"m2\":" + String(current_m2) + ",";
    json += "\"m3\":" + String(current_m3) + ",";
    json += "\"m4\":" + String(current_m4) + "}";
    server.send(200, "application/json", json);
  });

  server.begin();
}

// ============================================================
// 7. HAUPTSCHLEIFE (LOOP)
// ============================================================
void loop() {
  server.handleClient(); 

  if (isRunning) {
    requestAttitude();
    readAttitudeResponse();

    float rollCorrection = calculatePID(0.0, currentRoll, pid_roll_integral, pid_roll_last_error);
    float pitchCorrection = calculatePID(0.0, currentPitch, pid_pitch_integral, pid_pitch_last_error);
    
    last_pid_time = micros();

    rollCorrection = rollCorrection * algo_strength;
    pitchCorrection = pitchCorrection * algo_strength;

    int thr = BASE_THROTTLE;
    
    int m1 = thr - rollCorrection + pitchCorrection; 
    int m2 = thr - rollCorrection - pitchCorrection; 
    int m3 = thr + rollCorrection + pitchCorrection; 
    int m4 = thr + rollCorrection - pitchCorrection; 

    setMotors(m1, m2, m3, m4);
    delay(10); 
  } else {
    static long lastSafety = 0;
    if (millis() - lastSafety > 500) {
      setMotors(1000, 1000, 1000, 1000); 
      lastSafety = millis();
    }
  }
}