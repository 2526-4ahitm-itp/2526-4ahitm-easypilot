---
title: 2025-12-23 Sprintplanung Sprint 2
date: 2025-12-23
---

Zeit: 15:45 – 16:00 · Ort: Meet

> Im ursprünglichen AsciiDoc-Protokoll stand im Kopf irrtümlich der 25.11.2025. Die Datei und die
> Inhalte gehören zur Planung am 23.12.2025.

## Teilnehmer:innen

- David Windischbauer
- Simon Eder

## User Story: Motoren einzeln ansteuern

*Als Drohnenpilot möchte ich mittels Raspberry Pi eine Tonleiter bzw. Melodie wie bei einer
Taurus-Lokomotive abspielen können, um zu testen, ob die Motoren einzeln ansteuerbar sind.*

### Definition of Done

- Eine voreingespielte Tonfolge wird abgespielt.
- Jeder Motor kann einzeln angesteuert werden.
- Tonhöhe und Dauer der Töne sind einstellbar.
- Die Länge der Sequenz ist einstellbar.

---

| Wer | Was |
| --- | --- |
| David | ersten Test der Motorsteuerung durchführen |
| Simon, David | MAVLink-Python-Bibliothek für die Motorsteuerung analysieren |
| Simon | einzelne Motoren per MAVLink-Befehlen für die Tonleiter ansteuern |
| David | Sequenzen für die Tonleiter erstellen (2D-Array) |
