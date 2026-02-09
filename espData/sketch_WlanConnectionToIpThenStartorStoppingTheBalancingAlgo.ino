#include <WiFi.h>
#include <WebServer.h>

// ============================================================
// 1. EINSTELLUNGEN
// ============================================================

// WLAN (Hotspot Daten)
const char* ssid = "David´s Iphone";
const char* password = "123456789";

// UART Verbindung zum Flight Controller
// Wähle hier Pins, die auf deinem Board frei sind!
#define FC_TX_PIN 17  // Verbinde dies mit dem RX Pin am Flight Controller
#define FC_RX_PIN 18  // Verbinde dies mit dem TX Pin am Flight Controller
#define FC_BAUD 115200

// PID Parameter (Vorsichtig anfangen!)
float KP = 1.5;
float KI = 0.0;
float KD = 0.8;

// Gas Einstellungen
int BASE_THROTTLE = 1050; // Leerlauf (muss hoch genug sein, damit Motoren drehen)
int MAX_THROTTLE = 1800;

// ============================================================
// 2. GLOBALE VARIABLEN
// ============================================================
WebServer server(80);
bool isRunning = false; // Steuert, ob der Loop aktiv ist

// Drohnen Status
float currentRoll = 0.0;
float currentPitch = 0.0;

// PID Speicher
float pid_roll_integral = 0, pid_roll_last_error = 0;
float pid_pitch_integral = 0, pid_pitch_last_error = 0;
unsigned long last_pid_time = 0;

// Serial1 nutzen wir für den Flight Controller
HardwareSerial FCSerial(1); 

// ============================================================
// 3. MSP PROTOKOLL FUNKTIONEN
// ============================================================

// Hilfsfunktion: MSP Paket senden
void sendMSP(uint8_t cmd, uint8_t *data, uint8_t n_bytes) {
  uint8_t checksum = 0;
  
  FCSerial.write('$');
  FCSerial.write('M');
  FCSerial.write('<');
  FCSerial.write(n_bytes);
  checksum ^= n_bytes;
  
  FCSerial.write(cmd);
  checksum ^= cmd;
  
  for (int i = 0; i < n_bytes; i++) {
    FCSerial.write(data[i]);
    checksum ^= data[i];
  }
  
  FCSerial.write(checksum);
}

// Motoren setzen (MSP_SET_MOTOR = 214)
void setMotors(int m1, int m2, int m3, int m4) {
  // Begrenzung auf 1000-2000
  m1 = constrain(m1, 1000, 2000);
  m2 = constrain(m2, 1000, 2000);
  m3 = constrain(m3, 1000, 2000);
  m4 = constrain(m4, 1000, 2000);

  // Payload vorbereiten: 8 Motoren (wir nutzen 4), je 2 Bytes (uint16_t)
  // Little Endian Formatierung ist auf ESP32 Standard
  uint16_t motors[8] = {(uint16_t)m1, (uint16_t)m2, (uint16_t)m3, (uint16_t)m4, 1000, 1000, 1000, 1000};
  
  sendMSP(214, (uint8_t*)motors, 16); // 16 Bytes Payload
}

// Lage abfragen (MSP_ATTITUDE = 108)
void requestAttitude() {
  sendMSP(108, NULL, 0);
}

// Einfacher Parser für die Antwort (Blockierend für Einfachheit, besser wäre State Machine)
void readAttitudeResponse() {
  unsigned long start = millis();
  while (FCSerial.available() < 6 && millis() - start < 10) {
    // Warte kurz auf Daten
    delay(1);
  }

  if (FCSerial.available() >= 6) {
    // Wir suchen den Header (sehr vereinfacht)
    if (FCSerial.read() == '$' && FCSerial.read() == 'M' && FCSerial.read() == '>') {
      uint8_t size = FCSerial.read();
      uint8_t cmd = FCSerial.read();
      
      if (cmd == 108 && size >= 6) {
        int16_t roll, pitch, yaw;
        FCSerial.readBytes((char*)&roll, 2);
        FCSerial.readBytes((char*)&pitch, 2);
        FCSerial.readBytes((char*)&yaw, 2);
        
        // Checksum lesen (verwerfen wir hier der Einfachheit halber)
        FCSerial.read(); 

        currentRoll = roll / 10.0;
        currentPitch = pitch / 10.0;
      }
    }
    // Buffer leeren
    while(FCSerial.available()) FCSerial.read();
  }
}

// ============================================================
// 4. PID LOGIK
// ============================================================
float calculatePID(float target, float current, float &integral, float &last_error) {
  float error = target - current;
  
  // Zeitdifferenz berechnen
  unsigned long now = micros();
  float dt = (now - last_pid_time) / 1000000.0;
  if(dt <= 0) dt = 0.001;

  // Integral (mit Begrenzung)
  integral += error * dt;
  integral = constrain(integral, -50, 50);

  // Derivative
  float derivative = (error - last_error) / dt;

  last_error = error;
  
  return (KP * error) + (KI * integral) + (KD * derivative);
}

// ============================================================
// 5. WEBSEITEN & SETUP
// ============================================================

void handleRoot() {
  String html = "<html><head><meta name='viewport' content='width=device-width, initial-scale=1'></head>";
  html += "<body style='font-family:sans-serif; text-align:center;'>";
  html += "<h1>Flight Controller Bridge</h1>";
  html += "<p>Status: <b style='color:" + String(isRunning ? "green":"red") + ";'>" + String(isRunning ? "AKTIV" : "GESTOPPT") + "</b></p>";
  html += "<p>Roll: " + String(currentRoll) + " | Pitch: " + String(currentPitch) + "</p>";
  html += "<a href='/start'><button style='padding:20px;background:green;color:white;width:100%;margin-bottom:10px;'>START BALANCE</button></a><br>";
  html += "<a href='/stop'><button style='padding:20px;background:red;color:white;width:100%;'>NOT-AUS / STOP</button></a>";
  html += "</body></html>";
  server.send(200, "text/html", html);
}

void setup() {
  Serial.begin(115200); // USB Debugging
  
  // Verbindung zum Flight Controller initialisieren
  // RX am ESP -> TX am FC | TX am ESP -> RX am FC
  FCSerial.begin(FC_BAUD, SERIAL_8N1, FC_RX_PIN, FC_TX_PIN); 
  Serial.println("Verbinde mit Flight Controller...");

  // WLAN
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWLAN Verbunden: " + WiFi.localIP().toString());

  // Webserver
  server.on("/", handleRoot);
  
  server.on("/start", []() {
    isRunning = true;
    pid_roll_integral = 0; // PID Reset
    pid_pitch_integral = 0;
    last_pid_time = micros();
    Serial.println("START: Balancing aktiviert.");
    handleRoot();
  });

  server.on("/stop", []() {
    isRunning = false;
    setMotors(1000, 1000, 1000, 1000); // Sofort Motor aus
    Serial.println("STOP: Motoren aus.");
    handleRoot();
  });

  server.begin();
}

// ============================================================
// 6. HAUPTSCHLEIFE (LOOP)
// ============================================================
void loop() {
  server.handleClient(); // Check WLAN Befehle

  if (isRunning) {
    // A. Daten vom FC holen
    requestAttitude();
    readAttitudeResponse();

    // B. PID Berechnen
    // Da wir requestAttitude nutzen, haben wir eine kleine Zeitverzögerung,
    // das ist für einfache Tests okay.
    float rollCorrection = calculatePID(0.0, currentRoll, pid_roll_integral, pid_roll_last_error);
    float pitchCorrection = calculatePID(0.0, currentPitch, pid_pitch_integral, pid_pitch_last_error);
    
    // PID Zeit Update für den nächsten Durchlauf
    last_pid_time = micros();

    // C. Motoren mischen (Quad X)
    int thr = BASE_THROTTLE;
    
    int m1 = thr - rollCorrection + pitchCorrection; // Hinten Rechts
    int m2 = thr - rollCorrection - pitchCorrection; // Vorne Rechts
    int m3 = thr + rollCorrection + pitchCorrection; // Hinten Links
    int m4 = thr + rollCorrection - pitchCorrection; // Vorne Links

    // D. An FC senden
    setMotors(m1, m2, m3, m4);

    // E. Debugging (nicht zu oft printen, das bremst!)
    // Serial.printf("R: %.2f P: %.2f | M1: %d\n", currentRoll, currentPitch, m1);

    // Loop Frequenz begrenzen (ca 100Hz = 10ms)
    delay(10); 
  } else {
    // Sicherheits-Funktion: Wenn nicht running, sende sicherheitshalber ab und zu "0 Gas"
    static long lastSafety = 0;
    if (millis() - lastSafety > 500) {
      setMotors(1000, 1000, 1000, 1000);
      lastSafety = millis();
    }
  }
}