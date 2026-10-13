---
title: Testbericht Liftoff-Hover
date: 2026-09-28
---

## Aufbau

| | |
|---|---|
| Simulator | Liftoff 1.7.6, Free Flight, Level „Straw Bale“, Standard-Drohne (Armattan Mongoose), Acro |
| Middleware | `simulator/liftoff-hover/hover.py`, 250 Hz |
| Eingabe | Testskript über vJoy (Test 1 und 2), danach DJI-Controller des Teams |
| Telemetrie | UDP `127.0.0.1:9001`, 15 Floats |

Die Testflüge 1 und 2 hat ein Skript geflogen: armen, mit festem Gas steigen, Hover einschalten,
loggen. So ist der Ablauf reproduzierbar.

## Test 1: Hover nach dem Steigen

- Hover bei ~19 m/s Steigrate eingeschaltet.
- **Lage und Position:** exakt waagrecht, horizontal 0 cm Drift.
- **Fehler:** Die Höhe stieg dauerhaft mit 0,6 m/s weiter. Der Höhenregler hat nur die
  Geschwindigkeit gedämpft, das Integral war noch aus. Das geschätzte Schwebegas (35 %) lag über
  dem echten (~27 %).
- **Fix:** Die Höhe läuft jetzt über eine Soll-Steigrate mit Integral auf den Steigratenfehler. Die
  Höhe wird nach spätestens 1,5 s fixiert.

## Test 2: Hover im Steigflug mit Seitwärtsfahrt

- Hover bei 16 m/s nach oben und 2,6 m/s seitlich eingeschaltet.

| Zeit nach Einschalten | Zustand |
|---|---|
| 0–1,5 s | Bremsen, bis 25° Gegenneigung |
| ~2 s | horizontal gestoppt (0,1 m/s), Position fixiert |
| ~5 s | Höhe steht bei 57,43 m |
| 5–12 s | keine Bewegung mehr messbar (Position und Höhe auf ±1 cm), Heading −0,1° |

Das Schwebegas pendelte sich bei **28 %** ein.

## Mit echtem Controller

Mit dem DJI-Controller des Teams lief das Durchreichen 1:1. Das Armen klappte erst, als zwei Dinge
klar waren:
- Das Liftoff-Fenster muss den Fokus haben.
- Nur der Gasstick darf nach unten, nicht beide Sticks wie beim DJI-Armen.

## Automatisierte Tests

Dieselben Szenarien laufen als Regler-Tests im geschlossenen Kreis (`test_hover.py`) in CI:
- Abbremsen aus 6 m/s
- Halten von Position, Höhe und Heading
- falsch geschätztes Schwebegas (0,30 statt 0,45)
- Stick-Grenzen
- Lage-Konventionen
