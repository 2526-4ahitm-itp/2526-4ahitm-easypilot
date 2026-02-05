#include <WiFi.h>
#include <WiFiUdp.h>

// --- KONFIGURATION ---
const char* ssid = "DEIN_WLAN_SSID";
const char* password = "DEIN_WLAN_PASSWORT";

// Broadcast IP
const char* udpAddress = "255.255.255.255";
const int udpPort = 5000;

WiFiUDP udp;

// Simulierte Werte
float roll = 0;
float pitch = 0;
float yaw = 0;
int m1 = 1000;
int m4 = 1000;

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
    Serial.print("IP Adresse: ");
    Serial.println(WiFi.localIP());
}

void loop() {
    // 1. Daten simulieren
    // Werte in Radians (-1.0 bis 1.0 entspricht ca. -57 bis +57 Grad)
    roll = random(-100, 100) / 100.0;
    pitch = random(-100, 100) / 100.0;
    yaw = random(-100, 100) / 100.0;

    // Motoren simulieren (1000 - 2000)
    m1 = random(1000, 2000);
    m4 = random(1000, 2000);

    // 2. JSON String bauen
    // Format passend zur App: {"roll": ..., "pitch": ..., "yaw": ..., "m1": ..., "m4": ...}
    String json = "{";
    json += "\"roll\":" + String(roll) + ",";
    json += "\"pitch\":" + String(pitch) + ",";
    json += "\"yaw\":" + String(yaw) + ",";
    json += "\"m1\":" + String(m1) + ",";
    json += "\"m4\":" + String(m4);
    json += "}";

    // 3. UDP Paket senden
    udp.beginPacket(udpAddress, udpPort);
    udp.print(json);
    udp.endPacket();

    // Debug Ausgabe
    Serial.println("Gesendet: " + json);

    delay(50); // 20Hz
}
