#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>

void setup() {
  Serial.begin(115200);
  WiFi.begin("Sim", "123456789");
  while (WiFi.status() != WL_CONNECTED) { delay(500); }
  
  WiFiClientSecure client;
  client.setInsecure();
  
  Serial.println("Connecting to ngrok via WiFiClientSecure...");
  if (client.connect("primate-finer-frankly.ngrok-free.app", 443)) {
    Serial.println("CONNECTED to ngrok SSL!");
    client.stop();
  } else {
    Serial.println("FAILED to connect to ngrok SSL");
  }
}
void loop() {}
