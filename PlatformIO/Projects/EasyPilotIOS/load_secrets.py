Import("env")
import configparser
import os

config = configparser.ConfigParser()
config_path = os.path.join(env.get("PROJECT_DIR"), "secrets.ini")
header_path = os.path.join(env.get("PROJECT_DIR"), "include", "secrets_auto.h")

# Default values
ssid     = "Sim"
password = "123456789"

if os.path.exists(config_path):
    config.read(config_path)
    if "secrets" in config:
        ssid     = config.get("secrets", "wifi_ssid", fallback=ssid).strip('"\'')
        password = config.get("secrets", "wifi_pass", fallback=password).strip('"\'')
else:
    print("Warning: secrets.ini not found. Using defaults.")

# Create include dir
os.makedirs(os.path.dirname(header_path), exist_ok=True)

# Write header
with open(header_path, "w") as f:
    f.write("// Auto-generated — do not edit\n")
    f.write(f'#define SECRETS_WIFI_SSID "{ssid}"\n')
    f.write(f'#define SECRETS_WIFI_PASS "{password}"\n')
