---
title: iOS-App
weight: 5
---

Die App (`EasyPilotIOS/`, SwiftUI) hat drei Tabs. Sie teilen sich genau einen
`WebSocketManager` und einen `MotionManager`, die `ContentView` erzeugt. So gibt es nie zwei
Verbindungen zur Drohne.

## Dashboard

Live-Sicht auf die Drohne:
- 3D-Modell (SceneKit, `drohne-compressed.usdz`), das der Telemetrie folgt
- Lage, Motoren und Akku; unter 14,0 V wird der Akku rot
- Verbindungsstatus, Hinweis auf simulierte Daten (`fc=false`)
- Neigung des iPhones, Safe-Test, manuelle IP

## Algorithms

Testmodi der Firmware starten und einstellen:
- BALANCE mit `baseThrottle`, `kPRoll`, `kPPitch`
- MANUAL
- SOUND, bei dem die Neigung des iPhones alle vier Motoren steuert: 0° → 1000, 45° → `maxPWM`,
  über 60° Notstopp

Parameter lassen sich als **Profile** speichern. Scharf schalten geht nur durch 1,5 s Halten.

## Simulator

Eine eigene Physik-Simulation auf dem Telefon:
- Zwei virtuelle Joysticks (Mode 2): links Gas/Yaw, rechts Pitch/Roll, mit Expo-Kurve
- Flugmodi RATE (Acro), BALANCE (nivelliert beim Loslassen) und POSHOLD (fliegt zur
  Loslass-Position zurück)
- Höhenhaltung mit Neigungskompensation
- Stabilisierung nur, wenn kein Finger auf dem Stick liegt; der Stick leuchtet dann grün
- Hoch- und Querformat

## LIVE-Modus

Derselbe Simulator-Tab kann die echte Drohne fliegen. Beim Scharfschalten sendet die App `ARM` und
`START_RC`, danach alle 100 ms ein `RC`-Paket aus den Joysticks. Fehlt ein Paket 500 ms lang,
stoppt die Firmware die Motoren. LIVE ist seit 28.05.2026 im Code, konnte aber wegen des
Air-Unit-Defekts nicht mehr im Flug getestet werden.

## Bekannter Bug

Meldet die Firmware `"mode":"RC"`, zeigt die App IDLE an. Der Algorithms-Tab blendet dann den
STOP-Button aus. Der Fix ist geplant:
[Change `2026-10-13-fix-ios-rc-mode`](https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot/tree/main/openspec/changes/2026-10-13-fix-ios-rc-mode).

## Tests

Swift-Testing-Unit-Tests für das Befehlsformat (inkl. Dezimalpunkt bei österreichischer Region),
das Telemetrie-Decoding, die Sound-Mode-Rechnung und die Profile; ein UI-Smoke-Test öffnet alle
drei Tabs. Sie laufen in GitHub Actions auf einem macOS-Runner.
