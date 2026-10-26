## Context

- `simulator/liftoff-hover/hover.py` liest Liftoffs UDP-Telemetrie mit Position, Quaternion, Gyro und Input bei rund 500 Hz. Er schreibt Sticks über vJoy und regelt mit 250 Hz.
- Gemessen am 28.09.2026: Bremsen aus 16 m/s, danach Position auf ±1 cm. Die Lagekonventionen (Unity, linkshändig, Y oben) sind durch Tests abgesichert.
- **Grenzen des Hover-Reglers:**
  - Neigung höchstens 25°.
  - Rate-Kurve linear angenommen (200 °/s bei Vollausschlag).
  - Schub als linear im Gas angenommen.

  Für Schweben reicht das, für ein Rennen nicht.
- Liftoff gibt **nur den Zustand der eigenen Drohne** heraus, keine Tore und keine Hindernisse.
- Kamera-FOV in Liftoff: 125° (`Config/System.xml`).
- Liftoff hat einen Strecken-Editor. Eigene Strecken liegen unter `AppData\LocalLow\LuGus Studios\Liftoff\Tracks`; der Ordner ist auf dem Team-PC noch leer. Ob Tor-Positionen dort lesbar gespeichert sind, klärt Spike 0.1.

## Goals / Non-Goals

**Goals**
- Autonome Runde auf einer eigenen Liftoff-Strecke, bei 100 % Geschwindigkeit, 10 Runden ohne Fehler.
- Rundenzeit unter der besten Zeit des Teams, gemessen mit Controller.
- Tor-Erkennung im Kamerabild mit Live-Overlay.
- Zielflug zu einer GPS-Koordinate, 1–3 m über Boden, 0 Kollisionen bei 10 Zielen.
- Robuster Ablauf am Tag der offenen Tür: Reset per Knopf, Bestenliste, unter 30 s pro Wechsel.

**Non-Goals**
- Schlagen von erfahrenen FPV-Pilot:innen (Forschungsniveau, z. B. UZH „Swift“ 2023).
- Reinforcement Learning; der Plan nutzt klassische Planung und Regelung, die das Team erklären kann.
- Fremde Liftoff-Level mit unbekannter Szenerie für die Kollisionsvermeidung.
- Die echte Drohne (Air Unit defekt).

## Architektur

```
                 ┌──────────────── simulator/autopilot ─────────────────┐
 Liftoff ──UDP──►│ adapters/liftoff  ──► state (pos, vel, quat, rates)  │
   ▲             │                         │                            │
   │ vJoy        │ perception/  ◄── dxcam │   track/  (Streckendatei)   │
   └─────────────│   gates (YOLO+PnP) ──► estimator (Tor-Fusion, EKF)  │
                 │                         │                            │
                 │ planning/   racing_line  |  waypoint (A*, lokal)     │
                 │                         ▼                            │
                 │ control/    trajectory_tracker → attitude → rates    │
                 │             → stick (inverse Rate-Kurve, Schubkurve) │
                 │                                                      │
                 │ race/       Zeitmessung, Bestenliste (Web), Reset    │
                 └──────────────────────────────────────────────────────┘
 Web-Simulator ◄─ adapters/websim (WebSocket, gleiches Interface) ─┘   (falls Zielflug dort)
```

`Adapter` ist ein schmales Interface: `state()`, `send_sticks(thr, yaw, pitch, roll)`, `reset()`. Dadurch laufen Planung und Regelung unverändert auf Liftoff und auf dem eigenen Simulator. Auf dem Web-Simulator sind auch Tests ohne Liftoff möglich.

## Decisions

### Tore: Streckendatei zuerst, Kamera darauf aufbauend
- **Streckendatei:** Die Streckendatei liefert exakte Tor-Posen ohne Fehler. Damit lassen sich Planung und Regelung entwickeln, bevor die Erkennung existiert.
- **Kamera:** Die Kamera-Erkennung nutzt die Datei, um **Trainingsbilder automatisch zu beschriften**:
  - Drohnenpose und Torpose sind bekannt.
  - Daraus folgen die Torecken im Bild über Kameramodell, FOV 125° und Kamera-Uptilt der Drohne.
  - Tausende beschriftete Bilder entstehen ohne Handarbeit.
- **Fallback:** Klappt Spike 0.1 nicht, weil die Datei nicht lesbar ist, werden die Torpositionen einmalig abgeflogen. Dabei fliegt man durch jedes Tor und speichert die Pose.

### Erkennung: YOLO-Keypoints + PnP
- YOLO v8/11 im Pose-Modus erkennt pro Tor die 4 Innenecken.
- `cv2.solvePnP` mit bekannter Torgröße ergibt die Torpose relativ zur Kamera. Zusammen mit der Telemetrie wird daraus die Weltpose.
- Ein Filter pro Tor (Kalman) fusioniert Datei und Kamera. Weicht ein Tor ab, folgt die Linie der Kamera.
- Aufnahme mit `dxcam` (Desktop Duplication, > 100 fps). Inferenz eines Nano-Modells auf der RTX 5060 Ti: wenige Millisekunden.
- Latenz von Bild zu Pose wird gemessen und über die Telemetrie-Zeitstempel ausgeglichen.

### Ideallinie
- Wegpunkte in den Tormitten, Durchflugrichtung entlang der Tornormalen.
- Bahn als stückweises Polynom mit minimalem Snap (glatt, fliegbar).
- Geschwindigkeitsprofil über die Bogenlänge, vorwärts/rückwärts begrenzt durch:
  - maximale Beschleunigung aus dem Schub-Gewicht-Verhältnis (vermessen)
  - maximale Querbeschleunigung in Kurven
  - Sicherheitsabstand zum Torrand
- Ein Parameter `aggressiveness` (0,5–1,0) skaliert alles. Damit lässt sich schrittweise bis „volle Geschwindigkeit“ testen.

### Renn-Regler
- Aus Soll-Position, -Geschwindigkeit und -Beschleunigung der Bahn wird die Soll-Beschleunigung (PD + Vorsteuerung). Daraus folgen **Schubvektor** und Schubbetrag.
- Lagefehler über Quaternionen (beliebige Neigung, kein 25°-Limit) → Soll-Drehraten → Stick.
- **Systemidentifikation statt Annahmen:**
  - Rate-Kurve der Drohne: Stick-Sprünge, Gyro messen, Tabelle invertieren.
  - Schubkurve: Gas gegen gemessene Beschleunigung, abhängig von der Geschwindigkeit.
  - Widerstand: Ausrollen ohne Gas.
- Die Drohne in Liftoff bekommt feste Rates (Betaflight-Standard), damit die Vermessung gültig bleibt.

### Zielflug und Kollisionsvermeidung
- **GPS:** fester Referenzpunkt (lat₀, lon₀) ↔ Simulator-Ursprung. Lokale Tangentialebene (ENU), auf wenige hundert Meter genau genug.
- **Hinderniskarte:**
  - in Liftoff aus der Streckendatei (eigene Hindernisse, Spike 0.1)
  - im Web-Simulator aus der Szene
  - daraus ein 3D-Belegungsgitter (0,25 m) mit Sicherheitsrand
- **Global:** A* auf dem Gitter, Kosten für Höhe außerhalb von 1–3 m. Danach Glättung zu einer fliegbaren Bahn wie bei der Rennlinie.
- **Lokal:**
  - Abstandsstrahlen gegen die Karte, simuliert wie ein Lidar.
  - Liegt ein Hindernis näher als der Bremsweg, wird gebremst und neu geplant.
- **Volle Geschwindigkeit:** Die Geschwindigkeit wird so begrenzt, dass der Bremsweg immer kleiner ist als die freie Strecke voraus. Schneller ist kollisionsfrei nicht möglich, und genau das zeigen die Tests.

### Wo läuft der Zielflug? (Entscheidung in Task 0.5)

| Option | Pro | Contra |
|---|---|---|
| Liftoff, eigene Strecke mit Hindernissen aus der Datei | eine Umgebung für alles, realistische Physik | nur Hindernisse, die wir selbst platzieren; Level-Szenerie (Bäume) unbekannt |
| Eigener Web-Simulator | volle Kontrolle über Karte, erfüllt zugleich Phase-2-Aufgabe §10.2 | Physik und Szene müssen erst gebaut werden (Change `2026-10-13-phase2-web-simulator`) |

**Empfehlung:** Liftoff mit eigener Strecke für den Tag der offenen Tür; der Web-Simulator folgt über den Adapter, wenn Zeit bleibt.

### Rennmodus
- Gate-Crossing: Ein Tor zählt, wenn die Drohnenposition zwischen zwei Telemetrie-Samples die Torebene innerhalb des Rahmens schneidet. Zeitmessung über Liftoff-Zeitstempel.
- Bestenliste als kleine lokale Webseite (FastAPI + statisches HTML) im Vollbild neben Liftoff, mit Name, Zeit und Platz. Die Daten bleiben lokal, Namen werden nach dem Tag gelöscht.
- Reset: vJoy-Taste, in Liftoff auf „Reset drone“ gelegt. Damit sind automatische Serienflüge und schnelle Wechsel möglich.
- Gleiche Drohne und gleiche Strecke für Mensch und Programm. Das Programm fliegt nach dem Menschen oder als „Zeit zum Schlagen“ vorher.

## Risks / Trade-offs

| Risiko | Gegenmaßnahme |
|---|---|
| Streckendatei nicht lesbar | Torposen einmalig abfliegen und speichern (Task 0.1 Fallback) |
| Liftoff nimmt Eingaben nur mit Fokus an | Vorführ-PC: Liftoff im Vordergrund, Bestenliste auf zweitem Bildschirm |
| vJoy/Telemetrie-Latenz bei Vollgas | Latenz messen, Vorsteuerung, `aggressiveness` < 1 als Notbremse |
| Erkennung versagt bei Licht/Effekten | Motion Blur aus, feste Grafikeinstellungen; Datei-Fallback bleibt aktiv |
| Liftoff-Update ändert Telemetrie/Controller-Dateien (schon passiert) | Liftoff-Version für den Tag einfrieren (Steam: Updates aus), Backup der InputSettings |
| Zu ehrgeizig für die Zeit | Gates mit Go/No-Go; Streckendatei-Rennen allein ist schon vorführbar |

## Open Questions

- Datum des Tags der offenen Tür.
- Zielflug in Liftoff oder im Web-Simulator (Task 0.5).
- Darf ein zweiter PC mit eigener Liftoff-Lizenz für ein echtes Kopf-an-Kopf-Rennen genutzt werden?
- Referenzpunkt für GPS (z. B. Schulhof der HTL Leonding), vom Team festzulegen.

## Stand der Umsetzung (18.10.2026)

Abweichungen vom ursprünglichen Plan, mit Grund:

- **Streckendatei:** Statt einer eigenen Strecke liegen alle offiziellen Liftoff-Rennen als XML
  in den Addressables-Bundles des Spiels. Checkpoint-ID = Instanz-ID des Tors. Die Angabe der
  Durchflugrichtung ist nicht einheitlich, sie wird aus der Torfolge bestimmt. Bezugspunkte
  unterscheiden sich je Tortyp und werden per Projektion ins Kamerabild gemessen.
- **Renn-Regler:** Statt Kaskade mit Neigungsgrenze ein Beschleunigungs-Regler mit
  Schubvektor, quadratischer Schubkurve, vorgesteuertem Luftwiderstand (0,033 1/m) und
  Störgrößenschätzung (INDI-ähnlich). Ohne Widerstandsmodell sackte die Drohne bei 27 m/s ~1 m ab.
- **Bildaufnahme:** GDI statt dxcam (kein zusätzlicher Treiber), Liftoff im 1080p-Fenster.
- **Erkennung:** Labels werden aus XML-Torposen + Telemetrie projiziert, keine Handarbeit.
  YOLOv8n-Pose mit 4 Eckpunkten; Kartenkorrektur über PnP und gefilterten Versatz pro Tor.
- **Liftoff-Eigenheiten:** Eingaben nur nach echter Fenster-Aktivierung, vJoy-Flush, VSync aus
  (siehe Hugo-Erklärung „Autonomes Rennen“).

Ergebnisse: Hugo-Testbericht „autonomes Rennen“.
