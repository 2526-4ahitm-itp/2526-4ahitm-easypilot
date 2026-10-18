# Tasks: Autonomes Rennen zum Tag der offenen Tür

Legende: `[x]` erledigt, `[~]` teilweise, `[ ]` offen. Stand 18.10.2026.

Zeitplan in Wochen **W1–W10**, rückwärts vom Tag der offenen Tür (TdoT = Ende W10). Datum vom Team
zu ergänzen. Liegt der TdoT früher, fallen zuerst Phase 4 (Kamera-Erkennung) und Phase 5 (Zielflug)
weg. Das Rennen mit Streckendatei allein ist schon vorführbar.

Aufteilung (Vorschlag, vom Team zu bestätigen): **A** = Regelung, Planung, Liftoff (David),
**B** = Erkennung, Rennmodus, Web/UI (Simon). Jede Phase endet mit einem PR und einem Sprint-Review.

| Phase | Wochen | Meilenstein | Gate |
|---|---|---|---|
| 0 Spikes | W1 | Machbarkeit belegt | Go/No-Go für den ganzen Plan |
| 1 Kern + erste Runde | W2–W3 | autonome Runde bei 50 % | M8 |
| 2 Volle Geschwindigkeit | W4–W5 | 10 Runden bei 100 %, schneller als Team-Bestzeit | M9 |
| 3 Rennmodus | W5–W6 | Ablauf Mensch → Programm mit Bestenliste | M10 |
| 4 Kamera-Erkennung | W5–W8 | Runde mit verschobenen Toren, Live-Overlay | M11 |
| 5 Zielflug | W6–W9 | 10 GPS-Ziele, 0 Kollisionen | M12 |
| 6 Generalprobe | W10 | Probelauf mit Mitschüler:innen | TdoT |

## 0. Spikes (W1) – Machbarkeit

- [x] 0.1 [SPEC] Strecke im Liftoff-Editor bauen (6–8 Tore, 1 Hindernis), Datei unter `Tracks/` öffnen: stehen Tor-Positionen, Rotation und Größe darin? **Fallback:** Posen beim Durchfliegen per Telemetrie aufzeichnen. → Fallback nicht nötig: offizielle Strecken liegen als XML in den Spieldateien (UnityPy), `track.py`
- [x] 0.2 [GAP] Reset per vJoy-Taste: Taste in Liftoff auf „Reset drone“ legen, aus Python auslösen, Telemetrie-Sprung erkennen. → vJoy-Knopf 3 → Rewired-Aktion Reset, Sprung in der Telemetrie wird erkannt
- [x] 0.3 [GAP] Bildschirmaufnahme mit `dxcam`: fps und Latenz bei laufendem Liftoff messen (Ziel ≥ 60 fps, < 30 ms). → GDI-Aufnahme statt dxcam: 22 ms bei 1080p-Fenster
- [~] 0.4 [GAP] Drohne festlegen und Rates in Liftoff fixieren; Liftoff-Updates in Steam abschalten. → Armattan Mongoose, Raten gemessen; Liftoff-Updates abschalten noch offen
- [ ] 0.5 [SPEC] Entscheidung: Zielflug in Liftoff oder im Web-Simulator (Tabelle in `design.md`), Ergebnis in `design.md` eintragen.
- [ ] 0.6 [SPEC] Aufgabenänderung mit Datum und Grund mit Betreuer:in abstimmen, FSD §1.3 aktualisieren.
- **Gate:** 0.1 (oder Fallback) und 0.2 funktionieren → Plan gilt. Sonst Ziel neu schneiden.

## 1. Autopilot-Kern und erste autonome Runde (W2–W3) – A

- [x] 1.1 [GAP] `simulator/autopilot/` anlegen: `adapters/liftoff.py` (Telemetrie + vJoy aus `hover.py`), `Adapter`-Interface, `state.py`. → `simulator/autopilot/` mit telemetry, vjoy, liftoff (Sitzung), window
- [ ] 1.2 [GAP] `liftoff-hover` auf den Kern umstellen; bestehende 10 Tests müssen grün bleiben.
- [x] 1.3 [GAP] `track/`: Streckendatei einlesen → Liste von Toren (Mitte, Normale, Breite, Höhe). → `track.py` liest Rennen und Strecken, Tormaße je Typ
- [x] 1.4 [GAP] `planning/racing_line.py`: Wegpunkte durch die Tormitten, Bahn mit minimalem Snap, konstante Geschwindigkeit. → `planner.py`: Hermite-Spline + Geschwindigkeitsprofil
- [x] 1.5 [GAP] `control/tracker.py`: Bahnverfolgung mit dem bestehenden Kaskadenregler (Neigung ≤ 35°). → neuer Renn-Regler statt Kaskade mit 35°-Grenze (`control.py`)
- [x] 1.6 [GAP] `race/gates.py`: Torebenen-Durchgang erkennen, Runden- und Sektorzeiten. → `racer.py`: Torebenen-Durchgang, Zeiten
- [x] 1.7 [GAP] Tests: Strecken-Parser, Bahn geht durch alle Tormitten, Durchgangserkennung (synthetische Telemetrie). → `tests/test_racing.py`
- **M8:** autonome Runde mit 50 % Geschwindigkeit, alle Tore getroffen. ✓ 18.10.2026: Rennsieg auf Field Day, 3 Runden 59,154 s bei 80 %.

## 2. Volle Geschwindigkeit (W4–W5) – A

- [x] 2.1 [GAP] Systemidentifikation: Rate-Kurve (Stick-Sprünge ↔ Gyro), Schubkurve (Gas ↔ Beschleunigung), Widerstand (Ausrollen); Ergebnisse als JSON pro Drohne. → `sysid.py`, `calib_cam.py`, Ergebnis `drone.json`
- [x] 2.2 [GAP] Renn-Regler: Soll-Beschleunigung → Schubvektor → Quaternion-Lagefehler → Drehraten → Stick über inverse Rate-Kurve; keine Neigungsgrenze. → `control.py`, inkl. Luftwiderstand und Störgrößenschätzung
- [x] 2.3 [GAP] Geschwindigkeitsprofil an der Leistungsgrenze (Vorwärts-/Rückwärtsdurchlauf, Parameter `aggressiveness`). → Vorwärts-/Rückwärtsdurchlauf mit Widerstand und Steigung
- [~] 2.4 [GAP] Test-Harness: N Runden automatisch mit Reset; Rundenzeit, Torquote, minimaler Abstand zum Torrand, Abstürze als CSV. → Logs pro Lauf als CSV + `race_results.jsonl`; Serien mit Reset noch nicht
- [~] 2.5 [GAP] Geschwindigkeitsreihe 50 % → 70 % → 85 % → 100 %, jeweils 20 Runden, Ergebnisse im Sprint-Review. → Reihe 35/60/70/80/100 % je 1 Runde, 3 Runden bei 80 % (Liftoff-gewertet); 20 Runden je Stufe offen
- [x] 2.6 [GAP] Regler-Tests im geschlossenen Kreis wie bei `test_hover.py`, mit vermessener Drohne. → `tests/test_racing.py` mit Modellfehlern
- **M9:** 10 Runden hintereinander bei 100 % ohne Fehler; Rundenzeit unter der besten Team-Zeit mit Controller.

## 3. Rennmodus für den TdoT (W5–W6) – B

- [ ] 3.1 [GAP] Ablauf-Steuerung: Modus „Mensch“ (Durchreichen, Zeitmessung) → Modus „Programm“; Wechsel per Taste.
- [ ] 3.2 [GAP] Bestenliste: lokale Webseite (Vollbild, zweiter Bildschirm), Name eintragen, Platzierung, Programmzeit als Referenz.
- [ ] 3.3 [GAP] Fehlstart, Absturz und verpasstes Tor behandeln (Lauf ungültig oder Strafzeit, Regel festlegen).
- [ ] 3.4 [GAP] Datenschutz: nur Vornamen/Spitznamen, Liste nach dem TdoT löschen.
- **M10:** kompletter Ablauf mit zwei Testpersonen, Wechsel unter 30 s.

## 4. Kamera-Erkennung (W5–W8) – B, mit A für die Projektion

- [x] 4.1 [GAP] Kameramodell: FOV 125°, Auflösung, Kamera-Uptilt der Drohne; Projektion Welt → Bild prüfen (Torecken auf Screenshot einzeichnen). → FOV 125°, Uptilt 42°, Projektion auf Screenshots geprüft
- [~] 4.2 [GAP] Datensammlung: Testflüge aufnehmen, Bilder automatisch mit projizierten Torecken beschriften (Ziel ≥ 5 000 Bilder, mehrere Level/Lichtverhältnisse). → 3209 Bilder automatisch beschriftet (`dataset.py`), bisher nur Straw Bale
- [x] 4.3 [GAP] YOLO-Pose-Modell (Nano) trainieren; Validierung: Ecken-Fehler in Pixel, Erkennungsrate. → YOLOv8n-Pose, Box-mAP50 0,79, Eckpunkte 0,85, 1,1 ms/Bild
- [~] 4.4 [GAP] PnP mit bekannter Torgröße → Torpose; Filter pro Tor, Fusion mit Streckendatei. → `detector.py`: PnP + Korrektur der Karte, im Flug noch nicht getestet
- [~] 4.5 [GAP] Live-Overlay für Zuschauer:innen (Rahmen, Abstand, nächstes Tor). → `draw_overlay` gebaut, Fenster im Rennen offen
- [ ] 4.6 [GAP] Test: Tore in der Strecke um 1 m verschieben → Programm fliegt trotzdem durch.
- **M11:** Runde mit verschobenen Toren; Overlay läuft live mit ≥ 30 fps.

## 5. Zielflug mit Kollisionsvermeidung (W6–W9) – A

- [~] 5.1 [GAP] GPS ↔ Simulator-Meter über Referenzpunkt (ENU), Eingabe im Rennmodus-UI. → `nav.py` GeoReference; Eingabe-UI offen
- [~] 5.2 [GAP] Hinderniskarte aus Streckendatei (bzw. Web-Simulator-Szene) → 3D-Belegungsgitter mit Sicherheitsrand. → Belegungsgitter aus Sensorpunkten; Hindernisse aus der Strecken-XML noch nicht eingelesen
- [x] 5.3 [GAP] A*-Planung mit Höhenband 1–3 m, Glättung zu fliegbarer Bahn. → A* + Glättung (2,5D, Höhenband über Boden)
- [x] 5.4 [GAP] Lokales Ausweichen: Abstandsstrahlen gegen die Karte, Bremsweg-Regel, Neuplanung. → Bremsweg-Regel, Neuplanung bei neuen Hindernissen
- [~] 5.5 [GAP] Testreihe: 10 zufällige Ziele bei steigender Geschwindigkeit; Kollisionen, minimaler Abstand, Flugzeit. → im eigenen Modell 10/10 Ziele, 0 Kollisionen, 1,2–1,6 m; in Liftoff offen
- **M12:** 10 Ziele, 0 Kollisionen, Höhe immer 1–3 m.

## 6. Generalprobe und Doku (W10)

- [ ] 6.1 [GAP] Generalprobe mit Mitschüler:innen am Vorführ-PC, Probleme beheben.
- [ ] 6.2 [GAP] Checkliste für den Tag: Liftoff-Version, vJoy-Setup, Controller, Bildschirme, Reset-Taste, Backup-PC.
- [ ] 6.3 [SPEC] Hugo-Doku: Erklärung (Erkennung, Ideallinie, Renn-Regler, Planung), Anleitung „TdoT aufbauen“, C4-Komponenten aktualisieren, Präsentation ergänzen.
- [ ] 6.4 [SPEC] Specs `gate-racing`, `waypoint-navigation`, `race-event` auf den echten Stand setzen, Change archivieren.
