
// --- KONFIGURATION ---
const char* ssid = "IHR_WLAN_NAME";
const char* password = "IHR_WLAN_PASSWORT";

// Die lokale IP-Adresse Ihres Windows PCs (siehe Anleitung unten, wie man die findet)
const char* pcIp = "192.168.1.105";
const int port = 5000;

WiFiUDP udp;

// Simulierte Gyroskop-Werte
float gyroX = 0;
float gyroY = 0;
float gyroZ = 0;

void setup() {
    Serial.begin(115200);

// WLAN Verbindung
WiFi.begin(ssid, password);
Serial.print("Verbinde mit WLAN");
while (WiFi.status() != WL_CONNECTED) {
delay(500);
Serial.print(".");
}
Serial.println("\nVerbunden!");
}

void loop() {
// 1. Daten simulieren (oder hier echte Sensordaten auslesen)
gyroX = random(-100, 100) / 100.0; // Zufallswert zwischen -1.00 und 1.00
gyroY = random(-100, 100) / 100.0;
gyroZ = random(-100, 100) / 100.0;

// 2. JSON String bauen: {"x": 0.12, "y": -0.5, "z": 0.9}
String json = "{\"x\":";
json += String(gyroX);
json += ",\"y\":";
json += String(gyroY);
json += ",\"z\":";
json += String(gyroZ);
json += "}";

// 3. UDP Paket senden
udp.beginPacket(pcIp, port);
udp.print(json);
udp.endPacket();

// Debug Ausgabe im Serial Monitor
Serial.println("Gesendet: " + json);

// Kurze Pause (z.B. 20ms für 50Hz Update-Rate)
delay(20);
}