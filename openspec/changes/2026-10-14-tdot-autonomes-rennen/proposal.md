## Why

Phase 2 („Drohnensimulation mit Physik-Engine“, FSD §1.2) bekommt ein konkretes, vorführbares Ziel: Am Tag der offenen Tür fliegen Schüler:innen in Liftoff gegen ein Programm, das die Torbögen selbst erkennt und so schnell wie möglich durchfliegt (FSD §20.1). Dazu kommt ein Zielflug: GPS-Koordinate eingeben, die Drohne fliegt tief und ohne Kollision hin (§20.4).

Der Liftoff-Hover (§11) zeigt schon, dass Telemetrie und Regelung in Liftoff funktionieren. Er hält aber nur Punkte mit maximal 25° Neigung. Ein Rennen braucht drei Dinge zusätzlich:
- Wissen, wo die Tore sind
- eine schnelle Flugbahn
- einen Regler, der ihr bei voller Geschwindigkeit folgt

## What Changes

- **Gemeinsamer Autopilot-Kern** (`simulator/autopilot/`), entstanden aus `liftoff-hover`. Er enthält Telemetrie, vJoy, Regler und ein Adapter-Interface. Derselbe Code steuert damit Liftoff und später den eigenen Web-Simulator (§20, §10.2).
- **Tore aus der Streckendatei:** eigene Liftoff-Strecke, Tor-Positionen einlesen (§20.2).
- **Tore aus dem Kamerabild:** Bildschirmaufnahme des FPV-Bilds, YOLO-Modell, Lageschätzung per PnP, Fusion mit der Streckendatei, Live-Overlay (§20.2, US-14).
- **Schnelle Flugbahn:** Ideallinie durch die Tore mit Geschwindigkeitsprofil an der Leistungsgrenze der Drohne (§20.3).
- **Renn-Regler:** volle Lageregelung über Beschleunigungsvektor → Schubrichtung → Drehraten → Stick, mit vermessener Rate- und Schubkurve der Liftoff-Drohne (§20.3, US-11).
- **Zielflug mit Kollisionsvermeidung:** GPS → Simulator-Meter, Hinderniskarte, globale Planung, lokales Ausweichen, Neuplanung (§20.4, US-13).
- **Rennmodus für den Tag der offenen Tür:**
  - Zeitmessung über die Tore
  - Bestenliste im Browser
  - Reset per Knopf
  - Ablauf Mensch → Programm

  Dazu gehören §20.5 und US-12.
- **Test-Harness:** automatische Serienflüge mit Reset, Messung von Rundenzeit, Torquote, Abstand zum Torrand und Abstürzen. Läuft über Nacht, bei steigender Geschwindigkeit bis 100 % (§13, §20.3).

## Capabilities

### New Capabilities
- `gate-racing`: Tore finden (Datei + Kamera), Ideallinie, Renn-Regler, Zeitmessung (§20.2, §20.3, US-11, US-14)
- `waypoint-navigation`: GPS-Ziel, Hinderniskarte, kollisionsfreier Tiefflug (§20.4, US-13)
- `race-event`: Rennmodus, Bestenliste, Ablauf am Tag der offenen Tür (§20.5, US-12)

### Modified Capabilities
- keine. `liftoff-hover` bleibt erhalten; der Hover-Regler zieht in den gemeinsamen Kern um, Verhalten unverändert.

## Impact

- **Neuer Code:** `simulator/autopilot/` (Python 3.11), Abhängigkeiten nach Rückfrage:
  - `numpy`
  - `dxcam` (Bildschirmaufnahme)
  - `ultralytics` (YOLO)
  - `opencv-python` (PnP, Overlay)
- **Liftoff:**
  - eine eigene Strecke für den Tag der offenen Tür
  - vJoy-Taste für „Reset“ belegen
  - Drohnen-Rates fest einstellen und vermessen
- **Web-Simulator:** bekommt ein Adapter-Interface (WebSocket), falls der Zielflug dort läuft (Entscheidung in Task 0.5).
- **Doku/Präsentation:** Aufgabenänderung mit Datum und Grund, C4-Diagramme um Autopilot-Kern, Erkennung und Planung erweitern.
- **Hardware:** Vorführ-PC mit Windows, Liftoff, GPU (Davids PC mit RTX 5060 Ti reicht), zweiter Controller.
