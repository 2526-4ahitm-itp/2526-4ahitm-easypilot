---
title: "Autonomes Rennen in Liftoff"
weight: 4
---

Wie das Programm eine Liftoff-Rennstrecke allein und so schnell wie möglich fliegt
(Pflichtenheft §20, Code `simulator/autopilot`).

## Überblick

```
Liftoff ──UDP 100 Hz──► Telemetrie ──► Renn-Regler ──vJoy──► Liftoff
                                          ▲
           Rennlinie ◄── Torposen ◄── Streckendatei (XML aus dem Spiel)
                            ▲
           FPV-Bild ──► KI-Torerkennung (Korrektur)
```

Liftoff rechnet die Physik, unser Programm ist nur der „Pilot“: Es liest Position, Lage und
Geschwindigkeit und bewegt einen virtuellen Joystick (vJoy).

## 1. Wo sind die Tore?

Liftoff speichert jedes offizielle Rennen als XML in seinen Spieldateien. Darin stehen alle
Tore und Hindernisse mit Position, Drehung und Typ. Ein Rennen listet die Checkpoints in
Reihenfolge; die Checkpoint-ID ist die Instanz-ID des Tors auf der Strecke.

- Die **Größe** steckt oft im Namen: `AirgateBig240H300B` = Öffnung 2,40 m hoch, 3,00 m breit.
- Der **Bezugspunkt** ist je Typ verschieden: Torbögen stehen mit dem Fuß am Punkt,
  unsichtbare Checkpoint-Boxen haben ihn in der Mitte, MultiGP-Rahmen hängen auf Masten
  (Variante 01: Öffnung in 4,05 m Höhe, Variante 02: 6,45 m). Diese Werte haben wir gemessen,
  indem wir mögliche Höhen ins aufgezeichnete Kamerabild projiziert haben.
- Die Angabe „von links / von rechts“ ist in den Dateien nicht einheitlich. Die Durchflugrichtung
  wird deshalb aus der Reihenfolge (vorheriges → nächstes Tor) bestimmt.

Ob eine Annahme stimmt, zeigt Liftoff selbst: Im Race-Modus zählt nur eine Runde, in der jeder
Checkpoint getroffen wurde.

## 2. Rennlinie und Geschwindigkeit

- Durch alle Tormitten läuft ein glatter Hermite-Spline; jedes Tor wird senkrecht durchflogen.
- Entlang der Linie wird die Höchstgeschwindigkeit begrenzt durch
  - die Querbeschleunigung in Kurven (v²·Krümmung),
  - Beschleunigen und Bremsen (Vorwärts- und Rückwärtsdurchlauf),
  - Luftwiderstand und Steigungen.
- Ein Faktor `aggressiveness` (0–1) skaliert alle Grenzen. So steigert man das Tempo schrittweise.

## 3. Renn-Regler

Der Hover-Regler aus dem Prototyp ist auf 25° Neigung begrenzt. Beim Rennen fliegt die Drohne
mit 60–75° Neigung, deshalb ein eigener Regler:

1. **Soll-Beschleunigung** = Vorsteuerung aus der Rennlinie + PD auf Position und Geschwindigkeit.
2. **Luftwiderstand** wird vorgesteuert (a = –0,033 · |v| · v, gemessen). Bei 27 m/s sind das
   ~25 m/s², also mehr als die Erdbeschleunigung.
3. **Störgrößenschätzung:** gemessene minus erwartete Beschleunigung, gefiltert. Sie gleicht
   Schubverlust bei hoher Geschwindigkeit und Modellfehler aus.
4. Daraus folgen **Schubrichtung und Schubbetrag**. Gas = √(a / k), weil der Schub quadratisch mit
   dem Gas wächst.
5. **Lage → Drehraten:** zuerst die Neigung, danach das Heading. Die Drehraten werden über die
   **umgekehrte Betaflight-Rate-Kurve** der Drohne zu Stickwerten.

Das Drohnenmodell (Schwebegas, Schubkurve, Raten, Kamera) wird automatisch vermessen:
`sysid.py` und `calib_cam.py`, siehe [Referenz](../../reference/liftoff-autopilot).

## 4. Tore im Kamerabild erkennen

- **Datensatz ohne Handarbeit:** Weil Torposen (XML) und Kamerapose (Telemetrie + kalibrierte
  Kamera) exakt bekannt sind, lassen sich die vier Ecken jeder Toröffnung ins Bild projizieren.
  So entstehen tausende beschriftete Bilder pro Runde. Verdeckte Tore werden über einen
  Weiß-Anteil-Test aussortiert.
- **Modell:** YOLOv8n im Pose-Modus erkennt Tor und vier Eckpunkte, auf der RTX 5060 Ti in
  wenigen Millisekunden.
- **Korrektur der Karte:** Aus den vier Ecken und der Torgröße liefert `solvePnP` die Torposition.
  Daraus wird nur dann ein Versatz übernommen, wenn er sicher ist – sonst würde die Kamera mehr
  schaden als nützen (alle Regeln aus Tests in Liftoff, siehe Testbericht):
  - **Zuordnung in 3D:** Die Erkennung gehört zu dem Tor, dessen Kartenposition der PnP-Lösung
    räumlich am nächsten liegt (höchstens 2,5 m). Gleiche Tore in einer Reihe überdecken sich im
    Bild, die Tiefe trennt sie.
  - **Nur in der Torebene:** Entlang der Flugrichtung verfälscht die Verzögerung zwischen Bild und
    Telemetrie die Messung (30 ms bei 27 m/s ≈ 0,8 m), für den Durchflug zählt aber nur, wo das Tor
    seitlich und in der Höhe liegt.
  - **Robust:** Median aus mindestens 8 Messungen aus 4–25 m Abstand, kleine Streuung, Totzone
    0,6 m (Torbögen sind oben rund, ihre „Ecken“ nur gedacht). Starttor wird nie korrigiert.
  - **Linie einfrieren:** Ab 12 m vor einem Tor wird nichts mehr geändert – ein seitlicher Sprung
    bei Vollgas führt zum Crash. Spätere Messungen wirken in der nächsten Runde.
  - Die Rennlinie wird in einem eigenen Thread neu geplant (~60 ms für 3 Runden) und im Flug
    getauscht; der Regeltakt (100 Hz) bleibt davon unberührt.
- **Live-Overlay** für die Zuschauer:innen: erkannte Tore grün, Kartentore rot, korrigierte gelb.

## 5. Was Liftoff schwierig macht

| Problem | Lösung |
|---|---|
| Liftoff ignoriert simulierte Maus-/Tastatureingaben, solange Unity keine echte Fenster-Aktivierung bekommen hat; Screenshot-Werkzeuge nehmen den Fokus weg | Eigene Bildschirmaufnahme (GDI), Fokus per Fenster-Aktivierung, Menüs über vJoy-Knöpfe |
| vJoy schickt die zuletzt gesetzte Achse erst mit dem nächsten Bericht | nach jedem Schreiben eine unbenutzte Achse setzen |
| Direkt nach dem Belegen des vJoy-Geräts geht die erste Eingabe verloren | 0,5 s warten |
| VSync auf „jedes zweite Bild“: 30 fps, ~80 ms Verzögerung | VSync aus, Fenster 1920×1080: Telemetrie 100 Hz, ~20 ms |
| Race-Modus hält die Drohne während des Countdowns fest | nach Reset 4,5 s warten |

## Grenzen

- Gelände zwischen den Toren steht nicht in der Streckendatei. Abkürzungen über Hügel sind nicht
  gegen den Boden geprüft.
- Für jeden neuen Tortyp muss der Bezugspunkt einmal geprüft werden (oder die Kamera korrigiert ihn).
- Jede neue Drohne braucht einmal `sysid` und `calib_cam`.
