# Spezifikation: EasyPilot – Drohnensteuerung und Drohnensimulation

Stand: 13.10.2026 · Team: Simon Eder, David Windischbauer · 4AHITM, HTL Leonding

Dieses Dokument ist das Pflichtenheft (FSD) von EasyPilot. Die Capability-Specs unter
`openspec/specs/` verweisen mit `§N.M` auf die Abschnitte hier und halten pro Anforderung
fest, ob sie umgesetzt ist (`implemented`, `partial`, `not-implemented`).

## 1. Zweck und Zielbild

### 1.1 Phase 1 – Drohnensteuerung (07.10.2025 – 23.06.2026, abgeschlossen)

Eine FPV-Drohne (iFlight Nazgul ECO, Betaflight-Flight-Controller BLITZ ATF435) bekommt einen
ESP32-C3 SuperMini als Companion-Computer. Der ESP32 spricht per MSP mit dem Flight Controller
und per WLAN mit einer eigenen iOS-App. Die App zeigt die Lage der Drohne live als 3D-Modell,
steuert Testmodi (Balance, Sound, RC) und enthält einen Simulator zum Üben auf dem Handy.

### 1.2 Phase 2 – Drohnensimulation mit Physik-Engine (seit 14.09.2026)

Weil die echte Drohne nicht mehr fliegt (siehe 1.3), simuliert EasyPilot die Drohne.
Ziel ist, Flugverhalten, Steuerung und Assistenzfunktionen (z. B. Positionshalten) ohne
Hardware zu entwickeln, zu testen und vorzuführen. Dazu gibt es zwei Wege:

- **Web-Simulator:** eine Drohnensimulation mit Physik-Engine im Browser, aufbauend auf dem
  3D-Viewer in `webinterface/frontend` (React + three.js). Er wird über die LeoCloud ausgeliefert.
- **Liftoff-Hover-Prototyp:** ein Autopilot auf dem kommerziellen FPV-Simulator Liftoff
  (`simulator/liftoff-hover`). Liftoff liefert die Physik. Der Prototyp zeigt die
  Regelalgorithmen, die der Web-Simulator übernehmen soll.

### 1.3 Änderung der Aufgabenstellung

| Datum | Änderung | Grund |
|---|---|---|
| 14.09.2026 | Phase 1 „Drohnensteuerung“ → Phase 2 „Drohnensimulation mit Physik-Engine“ | Die DJI O4 Air Unit ist defekt: kein Videobild, keine Steuerung über Brille und Fernbedienung, keine Tests mit der echten Drohne. |
| *geplant, mit Betreuer:in abzustimmen* | Phase 2 wird konkret: autonomes Rennen durch Torbögen in Liftoff und Zielflug mit Kollisionsvermeidung, vorgeführt am Tag der offenen Tür als Rennen „Schüler:innen gegen Programm“ (§20) | Ein klares, vorführbares Ziel statt eines allgemeinen Simulators; der Liftoff-Hover-Prototyp zeigt, dass die Regelung in Liftoff funktioniert. |

## 2. Rollen

| Rolle | Beschreibung |
|---|---|
| Pilot:in | fliegt die echte Drohne bzw. den Simulator, nutzt die iOS-App |
| Nutzer:in Web-Simulator | fliegt die simulierte Drohne im Browser, ohne Installation |
| Entwickler:in | Teammitglied; baut, testet und deployt die Teilsysteme |
| Betreuer:in | Lehrkraft; bewertet Fortschritt anhand von Doku, Präsentation, Tests und Deployment |

## 3. Systemkontext und technische Leitplanken

### 3.1 Plattformen

- Drohne: iFlight Nazgul ECO (Quad-X, 4S/6S LiPo), BLITZ ATF435 mit Betaflight, DJI O4 Air Unit (defekt)
- Companion: ESP32-C3 SuperMini, Arduino-Framework über PlatformIO
- Mobil: iPhone, iOS 18.5+, SwiftUI
- Browser: aktuelle Desktop-Browser (Chrome, Firefox, Safari) für Web-Viewer und Web-Simulator
- Simulator-Prototyp: Windows, Liftoff (Steam), vJoy

### 3.2 Tech-Stack (verbindlich)

| Teil | Technik |
|---|---|
| Firmware | C++ (Arduino), `links2004/WebSockets`, `ArduinoJson 7` |
| iOS-App | Swift, SwiftUI, SceneKit, CoreMotion, Swift Testing / XCTest |
| Backend | Java 21, Quarkus 3.28 |
| Relay, MSP-Sender, Liftoff-Hover | Python 3.11 |
| Web-Viewer / Web-Simulator | React 19, Vite 7, three.js, @react-three/fiber |
| Doku | Hugo + Hextra (GitHub Pages), OpenSpec |
| CI | GitHub Actions |

### 3.3 Infrastruktur

- Backend und Web-Simulator laufen in der LeoCloud der HTL Leonding (Kubernetes), Namespace
  `student-it220270`, Host `it220270.cloud.htl-leonding.ac.at`.
- Container-Images liegen auf `ghcr.io/2526-4ahitm-itp/`.
- Drohne, iOS-App und Relay laufen im lokalen WLAN. UDP-Broadcasts erreichen nur Geräte im
  selben Netz.
- Doku und Präsentationen liegen auf GitHub Pages.

## 4. Hardware

### 4.1 Verdrahtung ESP32 ↔ Flight Controller

UART1 des ESP32-C3: GPIO 20 = RX (an FC-TX), GPIO 21 = TX (an FC-RX), 115200 Baud, 8N1,
gemeinsame Masse. Der USB-C-Port dient als serielle Konsole (USB-CDC).

### 4.2 Motoren und PWM

Quad-X mit vier Motoren M1–M4. Jeder Motorbefehl liegt im PWM-Bereich 1000–2000 µs;
1000 bedeutet „Motor aus“. Die Standalone-Web-Firmware begrenzt zusätzlich auf 1400.

### 4.3 Akku

4S-LiPo: 16,8 V voll, 14,0 V kritisch (Warnung in der App). Die Spannung liefert der FC über
`MSP_ANALOG`. Der Prozentwert verläuft linear von 13,0 V (0 %) bis 16,8 V (100 %).

## 5. Kommunikation

### 5.1 Discovery

Der ESP32 sendet alle 5 s `EASYPILOT:<IP>` per UDP-Broadcast an Port 4242. Die iOS-App hört
auf Port 4242 und verbindet sich automatisch. Kommt kein Beacon an (z. B. AP-Isolation), kann
die IP im Dashboard eingegeben werden.

### 5.2 Befehle (iOS → ESP32)

WebSocket `ws://<esp32>:81`, ein TEXT-Frame pro Befehl, JSON mit Feld `cmd`:
`ARM`, `DISARM`, `STOP`, `START_BALANCE`, `START_MANUAL`, `START_SOUND`, `TILT_SOUND`,
`START_RC`, `RC`. Dazu kommen die Klartext-Befehle `SAFE_TEST` und `SIMULATE`. Zahlen werden
immer mit Dezimalpunkt gesendet, unabhängig von der Region des Telefons.

### 5.3 Telemetrie (ESP32 → iOS)

Alle 100 ms (10 Hz) ein JSON-Frame mit `roll, pitch, yaw, m1–m4, voltage,
batteryPercentage, armed, mode, fc`. Ältere Firmware schickt nur `roll, pitch, yaw`. Die App
muss beides verstehen.

### 5.4 MSP (ESP32 ↔ Flight Controller)

MSP v1: `MSP_ATTITUDE (108)` alle 100 ms, `MSP_ANALOG (110)` alle 500 ms,
`MSP_SET_MOTOR (214)` bei jeder Änderung der Motorwerte. Frames mit falscher Prüfsumme
werden verworfen.

### 5.5 Relay

Ein Python-Relay nimmt Telemetrie per WebSocket (Port 8080) an und verteilt sie per
UDP-Broadcast (Port 4242) im LAN. Optional wird es über einen Ngrok-Tunnel von außen
erreichbar gemacht (`start_system.sh`). Ein zweites Skript (`websocket_sender.py`) liest den
FC per USB-Serial und stellt die Lage für den Web-Viewer auf `ws://localhost:8765` bereit.

## 6. Flugmodi der Firmware

| Modus | Verhalten | Auslöser |
|---|---|---|
| IDLE | Motoren 1000, keine Regelung | Start, `DISARM`, `STOP` |
| BALANCE | P-Regler auf Roll/Pitch um `baseThrottle` | `START_BALANCE` |
| MANUAL | Motor- und Lagewerte kommen vom Client | `START_MANUAL` |
| SOUND | alle 4 Motoren auf die PWM aus `TILT_SOUND` (max. 1000–1500) | `START_SOUND` |
| RC | Gas, Soll-Roll/-Pitch (±45°) und Yaw aus `RC`-Paketen, Regelung wie BALANCE | `START_RC` |

Alle Modi außer IDLE setzen voraus, dass die Drohne scharf geschaltet (`ARM`) ist.

## 7. Sicherheit

### 7.1 Fail-Safe

Nach dem Start ist die Drohne nicht scharf und alle Motoren stehen auf 1000. Bricht die
WebSocket-Verbindung in SOUND oder RC ab, stoppen die Motoren und die Firmware geht auf IDLE.

### 7.2 Watchdogs

- SOUND: 1 s ohne `TILT_SOUND` → Motoren 1000.
- RC: 500 ms ohne `RC` → Motoren aus, IDLE.
- FC: 2 s ohne gültige MSP-Antwort → `fc=false`. Ist die Drohne nicht scharf, liefert die
  Firmware simulierte Telemetrie für Vorführungen.
- iOS Sound Mode: Neigung des Telefons über 60° → Notstopp.
- Standalone-Web-Firmware: Heartbeat-Ausfall 1,5 s → FAILSAFE; Lage über 60° → CRASH;
  Start nur bei Lage unter 5°.

### 7.3 Zugangsdaten

WLAN- und OTA-Zugangsdaten stehen nie im Repository. Vorlagen (`*.example*`) zeigen das Format.

## 8. iOS-App

### 8.1 Dashboard

Live-Telemetrie (Lage, Motoren, Akku mit Warnfarbe unter 14,0 V), Verbindungsstatus,
3D-Modell der Drohne, das der Lage folgt, Neigung des iPhones, Safe-Test und manuelle IP.

### 8.2 Algorithms

Parameter für BALANCE, SOUND und MANUAL einstellen, die Modi auf der Drohne starten und
stoppen, Parameter als Profile speichern, umbenennen und löschen. Profile bleiben nach einem
Neustart erhalten. Hier liegt auch der Sound Mode: Die Neigung des iPhones steuert alle vier
Motoren gemeinsam.

### 8.3 Simulator

Physik-Simulation der Drohne auf dem Telefon: virtuelle Joysticks (Mode 2, Expo), Flugmodi
Rate, Balance und POSHOLD, Höhenhaltung, Hoch- und Querformat, Stabilisierung nur ohne
Finger auf dem Stick.

### 8.4 LIVE-Modus

Aus dem Simulator-Tab wird die echte Drohne gesteuert: `START_RC` beim Scharfschalten, danach
laufend `RC`-Pakete aus den Joysticks.

## 9. Standalone-Web-Firmware

Eine zweite Firmware (`PlatformIO/Projects/easypilot`) stellt ein eigenes Web-Dashboard auf
Port 80 bereit: zeit- oder beschleunigungsbasierter Start, Schwebe-Zustandsautomat,
Heartbeat-Watchdog und OTA-Updates. Sie dient für Tests am Tisch und ist unabhängig von der App.

## 10. Web-Viewer und Web-Simulator

### 10.1 Web-Viewer (vorhanden)

React-Seite, die das Drohnenmodell (`drohne-compressed.glb`) mit three.js darstellt und die
Lage aus einem WebSocket-Stream übernimmt.

### 10.2 Web-Simulator (Phase 2, Ziel)

- Physik-Engine für Starrkörper: Schub der vier Motoren, Schwerkraft, Luftwiderstand, Boden.
- Steuerung per Tastatur und Gamepad (Gamepad-API), Belegung Mode 2.
- Flugmodi Rate (Acro), Angle und Positionshalten (Hover wie im Liftoff-Prototyp).
- HUD mit Höhe, Geschwindigkeit, Lage, Gas und Modus.
- Läuft ohne Drohne und ohne lokales Netzwerk direkt aus der LeoCloud.

## 11. Liftoff-Hover-Prototyp

Middleware zwischen Funk-Controller und Liftoff. Im manuellen Modus reicht sie die Sticks
über vJoy weiter. Auf Knopfdruck bremst sie die Drohne ab und hält Position, Höhe und
Heading. Grundlage ist die UDP-Telemetrie von Liftoff (Position, Quaternion). Beim
Zurückschalten blendet sie 0,5 s lang zur manuellen Steuerung über.

## 12. Backend und Deployment

### 12.1 Backend

Quarkus-Dienst mit `GET /api/status`. Weitere Endpunkte für den Web-Simulator (z. B.
gespeicherte Flüge) sind möglich, aber nicht festgelegt.

### 12.2 Deployment

GitHub Actions baut bei Pushes auf `main` die Images `easypilot-backend` und `easypilot-web`.
Sie werden mit `kubectl` in die LeoCloud deployt. Ein Ingress verteilt `/api` ans Backend und
`/` an den Web-Simulator.

## 13. Qualitätssicherung

Jedes Teilsystem mit Logik hat automatisierte Tests. Alle Tests laufen bei jedem Push und
Pull Request in GitHub Actions und brauchen keine Secrets.

## 14. Dokumentation und Prozess

- Doku als Hugo-Seite nach Diátaxis (Erklärung, Anleitungen, Referenz) plus Projektteil
  (Sitzungsprotokolle, Sprint-Reviews, Berichte) und Präsentationen, veröffentlicht auf
  GitHub Pages.
- Anforderungen in OpenSpec, ein Spec pro Capability, mit Umsetzungsstatus.
- Ein Branch und ein Pull Request pro Thema, Conventional Commits mit deutschem Betreff.

## 15. Nicht-funktionale Anforderungen

| Anforderung | Wert |
|---|---|
| Telemetrie-Rate zur App | ≥ 10 Hz |
| Latenz Lageänderung → Anzeige | < 200 ms |
| Regeltakt Liftoff-Hover | 250 Hz |
| Web-Simulator Bildrate | ≥ 60 fps auf einem aktuellen Laptop (Ziel) |
| Physik-Takt Web-Simulator | fester Zeitschritt, unabhängig von der Bildrate (Ziel) |

## 16. User Stories mit Akzeptanzkriterien

**US-01 Live-Lage sehen.** Als Pilot:in will ich die Lage der Drohne live als 3D-Modell sehen.
Akzeptanz: Das Modell folgt Roll/Pitch/Yaw mit weniger als 200 ms Verzögerung; der
Verbindungsstatus ist sichtbar.

**US-02 Motoren einzeln ansteuern.** Als Pilot:in will ich die Motoren über die Neigung des
Telefons ansteuern (Sound Mode). Akzeptanz: Neigung 0° → 1000, 45° → Maximalwert, über 60° Notstopp.

**US-03 Drohne finden.** Als Pilot:in will ich, dass die App die Drohne ohne IP-Eingabe findet.
Akzeptanz: Verbindung innerhalb von 10 s nach App-Start im selben WLAN.

**US-04 Simulator am Handy.** Als Pilot:in will ich am Handy fliegen üben. Akzeptanz:
Joysticks, Flugmodi Rate/Balance/POSHOLD, Querformat.

**US-05 Echte Drohne aus dem Simulator.** Als Pilot:in will ich die echte Drohne mit den
Simulator-Joysticks steuern. Akzeptanz: LIVE-Modus sendet `RC`-Pakete; Abbruch stoppt die Motoren.

**US-06 Parameter speichern.** Als Entwickler:in will ich Regelparameter als Profile speichern.
Akzeptanz: Profile überleben einen Neustart.

**US-07 Hover im Simulator.** Als Pilot:in will ich im Simulator auf Knopfdruck schweben
(DJI-artig). Akzeptanz: Abbremsen aus dem Flug, danach Position und Höhe auf ±0,2 m halten.

**US-08 Fliegen im Browser.** Als Nutzer:in will ich die Drohne im Browser fliegen.
Akzeptanz: Start ohne Installation über die LeoCloud-URL, Steuerung per Tastatur oder Gamepad,
Physik mit Schwerkraft und Schub.

**US-09 Status prüfen.** Als Entwickler:in will ich prüfen, ob das Backend läuft.
Akzeptanz: `GET /api/status` antwortet mit 200.

**US-10 Nachvollziehbarer Projektstand.** Als Betreuer:in will ich Projektstand, Termine,
Meilensteine und Architektur an einer Stelle finden. Akzeptanz: Hugo-Seite mit Präsentation,
C4-Diagrammen, Sprint-Reviews und Sitzungsprotokollen, verlinkt im README.

**US-11 Autonome Runde.** Als Zuschauer:in will ich sehen, wie das Programm die Drohne in Liftoff
ohne Mensch durch alle Torbögen fliegt. Akzeptanz: 10 Runden hintereinander ohne verpasstes Tor
und ohne Absturz, bei voller Geschwindigkeit (§20.2, §20.3).

**US-12 Rennen gegen das Programm.** Als Schüler:in am Tag der offenen Tür will ich mit dem
Controller gegen das Programm fliegen und meine Zeit in einer Bestenliste sehen. Akzeptanz:
Zeitmessung automatisch über die Tore, Bestenliste auf dem Bildschirm, Umbau zwischen zwei
Läufen unter 30 s (§20.5).

**US-13 Zielflug mit Kollisionsvermeidung.** Als Pilot:in will ich eine GPS-Koordinate eingeben,
und die Drohne fliegt tief über dem Boden ohne Kollision dorthin. Akzeptanz: 10 zufällige Ziele,
0 Kollisionen, Flughöhe 1–3 m, bei voller Geschwindigkeit (§20.4).

**US-14 Tore sehen.** Als Zuschauer:in will ich am Bildschirm sehen, welche Tore das Programm
gerade erkennt. Akzeptanz: Live-Overlay mit Rahmen um erkannte Tore (§20.2).

## 17. Abnahme Phase 2

- Web-Simulator in der LeoCloud erreichbar, Drohne per Tastatur/Gamepad flugfähig (US-08)
- Positionshalten im Web-Simulator oder im Liftoff-Prototyp vorführbar (US-07)
- Tests und CI für alle Teilsysteme grün
- Doku und Präsentation aktuell (US-10)

## 18. Priorisierung

### Muss (Phase 2)
US-07, US-08, US-09, US-10, Deployment (§12.2), CI (§13)

### Soll
Angle- und Positionshalte-Modus im Web-Simulator (§10.2), HUD

### Kann (später)
Flüge aufzeichnen und abspielen, Mehrspieler, Hindernisse/Parcours, Anbindung der echten
Drohne an den Web-Simulator

## 19. Offene Punkte

- Welche Physik-Engine der Web-Simulator verwendet (eigene Integration oder Bibliothek).
- Termine und Meilensteine für den Rest von Phase 2.
- Reparatur oder Ersatz der DJI O4 Air Unit.
- Ob das Backend für den Web-Simulator Daten speichert (z. B. Bestzeiten, Flugaufzeichnungen).
- Datum des Tags der offenen Tür (bestimmt den Zeitplan in §20.6).
- Ob der Zielflug mit Kollisionsvermeidung in Liftoff oder im eigenen Web-Simulator läuft (§20.4).
- Ob in Liftoff eigene Strecken die Tor- und Hindernispositionen lesbar speichern (Spike, §20.2).

## 20. Autonomes Rennen zum Tag der offenen Tür (in Arbeit)

Plan und Tasks: `openspec/changes/2026-10-14-tdot-autonomes-rennen/`, Code `simulator/autopilot`.

**Stand 18.10.2026:** autonomer Rennsieg in Liftoff auf „01 – Field Day“ (3 Runden 59,154 s, von
Liftoff gewertet, bester Bot 1:33,7); eine Runde bei voller Geschwindigkeit 18,7 s. Torerkennung
per Kamera trainiert, Zielflug im eigenen Modell getestet.

### 20.1 Ziel

Am Tag der offenen Tür fliegen Schüler:innen in Liftoff mit dem Funk-Controller eine Strecke mit
Torbögen. Danach fliegt das Programm dieselbe Strecke autonom und so schnell wie möglich.
Eine Bestenliste zeigt beide Zeiten. Zusätzlich fliegt die Drohne auf Knopfdruck zu einer
eingegebenen GPS-Koordinate, tief über dem Boden und ohne Kollision.

### 20.2 Torbögen erkennen

- **Streckendatei:** Liftoff speichert alle offiziellen und eigenen Strecken als XML mit Position,
  Ausrichtung und Typ jedes Tors. Das ist der verlässliche Grundweg (umgesetzt für Torbögen und
  MultiGP-Rahmen; Bezugspunkte je Tortyp gemessen).
- **Kamera:** Ein Bilderkennungsmodell findet die Tore im FPV-Bild von Liftoff. Aus Bildposition
  und bekannter Torgröße wird die Lage relativ zur Drohne geschätzt. Das korrigiert Abweichungen
  und funktioniert auch auf Strecken ohne Datei.
- Live-Overlay der erkannten Tore für die Zuschauer:innen.

### 20.3 Schnell durchfliegen

- Ideallinie durch alle Tore in Reihenfolge, mit Geschwindigkeitsprofil an der Schub- und
  Neigungsgrenze der Liftoff-Drohne.
- Regler, der der Linie bei voller Geschwindigkeit folgt (volle Lageregelung, nicht nur 25°
  Neigung wie der Hover-Prototyp).
- Zeitmessung über das Durchqueren der Torebenen.

### 20.4 Zielflug mit Kollisionsvermeidung

- Eingabe einer GPS-Koordinate. Sie wird über einen festen Referenzpunkt in Simulator-Meter
  umgerechnet.
- Flughöhe 1–3 m über Boden, Hindernisse aus einer Hinderniskarte (Streckendatei bzw.
  Szenengeometrie im eigenen Web-Simulator).
- Globale Wegplanung auf der Karte, lokale Ausweichreaktion, Neuplanung während des Flugs.

### 20.5 Rennmodus am Tag der offenen Tür

- Ablauf: Schüler:in fliegt → Zeit landet in der Bestenliste → Programm fliegt dieselbe Strecke.
- Ein Knopf setzt die Drohne zurück (vJoy-Taste auf „Reset“ in Liftoff).
- Bestenliste und Overlay laufen lokal im Browser auf dem Vorführ-PC.
- Optional: echtes Kopf-an-Kopf-Rennen über den Liftoff-Mehrspieler mit einem zweiten PC.

### 20.6 Zeitplan

Rückwärts vom Tag der offenen Tür geplant, in Wochen W1–W10 (siehe `tasks.md` im Change).
Datum vom Team zu ergänzen.
