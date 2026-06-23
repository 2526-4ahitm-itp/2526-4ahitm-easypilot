#include <WiFi.h>
void test() {
  WiFi.begin("ssid", WPA2_AUTH_PEAP, "identity", "username", "password");
}
