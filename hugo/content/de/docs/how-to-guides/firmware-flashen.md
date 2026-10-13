---
title: Firmware flashen
weight: 1
---

Voraussetzung: [PlatformIO](https://platformio.org/) (CLI oder VS-Code-Erweiterung), ESP32-C3
SuperMini per USB-C.

{{% steps %}}

### WLAN eintragen

```bash
cd PlatformIO/Projects/EasyPilotIOS
cp secrets.ini.example secrets.ini
```

`secrets.ini` öffnen und `wifi_ssid` / `wifi_pass` eintragen. Die Datei ist in `.gitignore`.
`load_secrets.py` erzeugt daraus beim Build `include/secrets_auto.h`.

### Bauen und flashen

```bash
pio run --target upload
```

### Prüfen

```bash
pio device monitor
```

Nach dem Verbinden mit dem WLAN erscheint `Beacon on port 4242 every 5 s`. Ohne Flight
Controller meldet die Firmware nach 2 s `fc=false` und liefert simulierte Telemetrie.

{{% /steps %}}

## Standalone-Firmware statt Companion

Für das Web-Dashboard direkt auf dem ESP32 dasselbe in `PlatformIO/Projects/easypilot`
(`wifi_secrets.example.h` → `wifi_secrets.h`). Danach im Browser `http://<esp32>/` öffnen.
Weitere Uploads gehen per OTA (Hostname `ESP32-Drohne`).
