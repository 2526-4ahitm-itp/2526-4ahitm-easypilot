---
title: Hardware
weight: 5
---

| Teil | Modell | Hinweis |
|---|---|---|
| Rahmen | iFlight Nazgul ECO (Quad-X) | BNF-Modell |
| Flight Controller | BLITZ ATF435, Betaflight | Stabilisierung, ESC-Ansteuerung |
| Video/Funk | DJI O4 Air Unit (Pro) | **defekt** seit Phase 2 |
| Companion | ESP32-C3 SuperMini | PlatformIO, Board `esp32-c3-devkitm-1` |
| Akku | LiPo 4S | 16,8 V voll, 14,0 V kritisch |
| Funk (Simulator) | DJI-Controller per USB | Achsen: 0 Roll, 1 Pitch, 2 Gas, 3 Yaw |

## Verdrahtung ESP32 ↔ FC

| ESP32-C3 | FC |
|---|---|
| GPIO 20 (UART1 RX) | TX-Pad |
| GPIO 21 (UART1 TX) | RX-Pad |
| GND | GND |

115200 Baud, 8N1. Der USB-C-Port des ESP32 ist die serielle Konsole
(`ARDUINO_USB_MODE=1`, `ARDUINO_USB_CDC_ON_BOOT=1`).

## Motoren

M1 vorne links, M2 vorne rechts, M3 hinten links, M4 hinten rechts. PWM 1000 (aus) bis 2000.
Die Standalone-Firmware begrenzt auf 1400.

Spec: `hardware-platform`.
