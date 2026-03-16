Import("env")
import configparser
import os

config = configparser.ConfigParser()
config_path = os.path.join(env.get("PROJECT_DIR"), "secrets.ini")

if os.path.exists(config_path):
    config.read(config_path)
    if "secrets" in config:
        ssid = config.get("secrets", "wifi_ssid", fallback='"Sim"')
        password = config.get("secrets", "wifi_pass", fallback='"123456789"')
        
        # Ensure values are properly quoted for C++ macros
        if not ssid.startswith('"'): ssid = f'"{ssid}"'
        if not password.startswith('"'): password = f'"{password}"'
        
        env.Append(CPPDEFINES=[
            ("SECRETS_WIFI_SSID", ssid),
            ("SECRETS_WIFI_PASS", password)
        ])
else:
    print("Warning: secrets.ini not found. Using default WiFi credentials.")