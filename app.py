#include <WiFi.h>
#include <WebServer.h>

// ============================================================
// 1. EINSTELLUNGEN
// ============================================================
const char* ssid = "Sim";
const char* password = "123456789";

// Angepasste Pins für den ESP32-C3 Supermini (Serial 1)
#define FC_TX_PIN 21
#define FC_RX_PIN 20
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

// WICHTIG: Der ESP32-C3 hat nur UART 0 und UART 1. 
// Daher nutzen wir hier HardwareSerial(1) anstelle von (2).
HardwareSerial FCSerial(1);

// ... ab hier geht dein Code normal mit Punkt 3 (MSP PROTOKOLL) weiter ...
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

  m1 = constrain(m1, 1000, 2000);
  m2 = constrain(m2, 1000, 2000);
  m3 = constrain(m3, 1000, 2000);
  m4 = constrain(m4, 1000, 2000);

  current_m1 = m1;
  current_m2 = m2;
  current_m3 = m3;
  current_m4 = m4;

  uint16_t motors[8] = {
    (uint16_t)m1,
    (uint16_t)m2,
    (uint16_t)m3,
    (uint16_t)m4,
    1000,1000,1000,1000
  };

  sendMSP(214, (uint8_t*)motors, 16);
}

void requestAttitude() {
  sendMSP(108, NULL, 0);
}

void readAttitudeResponse() {

  if (FCSerial.available() >= 11) {

    if (FCSerial.read() == '$' && FCSerial.read() == 'M' && FCSerial.read() == '>') {

      uint8_t size = FCSerial.read();
      uint8_t cmd = FCSerial.read();

      if (cmd == 108) {

        int16_t roll, pitch, yaw;

        FCSerial.readBytes((char*)&roll, 2);
        FCSerial.readBytes((char*)&pitch, 2);
        FCSerial.readBytes((char*)&yaw, 2);

        FCSerial.read();

        currentRoll = roll / 10.0;
        currentPitch = pitch / 10.0;
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
.btn-stop{background:#dc3545;color:white;}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
</style></head><body>

<h2>FC Control Dashboard</h2>

<div class='box'>
Status: <strong id='status'>-</strong><br>
Roll: <span id='roll'>0</span> |
Pitch: <span id='pitch'>0</span>
</div>

<div class='box'>
<h3>Motoren</h3>
<div class='grid'>
<div>M4: <span id='m4'>-</span></div>
<div>M2: <span id='m2'>-</span></div>
<div>M3: <span id='m3'>-</span></div>
<div>M1: <span id='m1'>-</span></div>
</div>
</div>

<div class='box'>
Regler-Stärke: <span id='gv'>100</span>%<br>
<input type='range' min='0' max='200' value='100' style='width:90%' 
oninput='fetch("/set_gain?val="+this.value);document.getElementById("gv").innerText=this.value'>
</div>

<button class='btn-start' onclick='fetch("/start")'>START BALANCE</button>
<button class='btn-stop' onclick='fetch("/stop")'>NOT-AUS</button>

<script>
setInterval(()=>{
fetch('/data')
.then(r=>r.json())
.then(d=>{
document.getElementById('status').innerText=d.running?"AKTIV":"GESTOPPT";
document.getElementById('roll').innerText=d.roll;
document.getElementById('pitch').innerText=d.pitch;
document.getElementById('m1').innerText=d.m1;
document.getElementById('m2').innerText=d.m2;
document.getElementById('m3').innerText=d.m3;
document.getElementById('m4').innerText=d.m4;
});
},200);
</script>

</body></html>
)rawliteral";

// ============================================================
// SETUP
// ============================================================
void setup() {

  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("ESP32 startet...");
  Serial.println("Verbinde mit WLAN...");

  FCSerial.begin(FC_BAUD, SERIAL_8N1, FC_RX_PIN, FC_TX_PIN);

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WLAN verbunden!");
  Serial.print("ESP32 IP Adresse: ");
  Serial.println(WiFi.localIP());

  server.on("/", []() {
    server.send(200, "text/html", htmlDashboard);
  });

  server.on("/start", []() {
    isRunning = true;
    pid_roll_integral = 0;
    pid_pitch_integral = 0;
    last_pid_time = micros();
    server.send(200);
  });

  server.on("/stop", []() {
    isRunning = false;
    setMotors(1000,1000,1000,1000);
    server.send(200);
  });

  server.on("/set_gain", []() {
    algo_strength = server.arg("val").toFloat() / 100.0;
    server.send(200);
  });

  server.on("/data", []() {

    String j = "{";
    j += "\"running\":" + String(isRunning) + ",";
    j += "\"roll\":" + String(currentRoll) + ",";
    j += "\"pitch\":" + String(currentPitch) + ",";
    j += "\"m1\":" + String(current_m1) + ",";
    j += "\"m2\":" + String(current_m2) + ",";
    j += "\"m3\":" + String(current_m3) + ",";
    j += "\"m4\":" + String(current_m4);
    j += "}";

    server.send(200, "application/json", j);
  });

  server.begin();

  Serial.println("Webserver gestartet");
}

// ============================================================
// LOOP
// ============================================================
void loop() {
Serial.print("Roll: ");
Serial.print(currentRoll);
Serial.print(" Pitch: ");
Serial.println(currentPitch);
  server.handleClient();

  if (isRunning) {

    unsigned long now = micros();
    float dt = (now - last_pid_time) / 1000000.0;

    if (dt <= 0) dt = 0.001;

    last_pid_time = now;

    requestAttitude();
    readAttitudeResponse();

    float rC = calculatePID(0.0, currentRoll, pid_roll_integral, pid_roll_last_error, dt) * algo_strength;
    float pC = calculatePID(0.0, currentPitch, pid_pitch_integral, pid_pitch_last_error, dt) * algo_strength;

    setMotors(
      BASE_THROTTLE - rC + pC,
      BASE_THROTTLE - rC - pC,
      BASE_THROTTLE + rC + pC,
      BASE_THROTTLE + rC - pC
    );

    delay(5);

  } else {

    static long ls = 0;

    if (millis() - ls > 500) {
      setMotors(1000,1000,1000,1000);
      ls = millis();
    }
  }
}