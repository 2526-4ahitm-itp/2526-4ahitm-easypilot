---
title: 2026-11-03 Phase 2 – Iteration 2
date: 2026-11-03
---

{{< report-card commits="28" prs="10" newlines="19686" remlines="5837" modfiles="330" >}}

Zeitraum: 13.10. – 03.11.2026 · Stand 03.11.2026

Die Zahlen enthalten die Branches vom 13.10.2026, die in
[Iteration 1](../2026-10-13_phase_2_iteration_1) nicht mitgezählt wurden. Nicht mitgezählt sind
die aus Liftoff extrahierten Streckendateien (`simulator/autopilot/tracks/`), die am 18.10.2026
einmal eingecheckt und im nächsten Commit wieder entfernt wurden (je rund 387.000 Zeilen).

## Ziel

Phase 2 bekommt ein vorführbares Ziel für den Tag der offenen Tür: Ein Programm fliegt in Liftoff
autonom durch die Torbögen, so schnell wie möglich, und tritt gegen Schüler:innen an. Dazu kommt
ein GPS-Zielflug ohne Kollision (Change `2026-10-14-tdot-autonomes-rennen`, FSD §20).

## Umgesetzt

| Aufgabe | Status | Beleg |
|---|---|---|
| Hugo-Doku, OpenSpec mit Umsetzungsstatus, Pflichtenheft, reveal.js-Präsentation | erledigt | PR #61, #62, #65 |
| Liftoff-Hover-Middleware im Repo | erledigt | PR #59 |
| Deployment in der LeoCloud | live seit 14.10.2026 | PR #64, https://it220270.cloud.htl-leonding.ac.at/ |
| OpenSpec-Validierung in der CI | erledigt | PR #62 |
| Implementierungsplan für das autonome Rennen | erledigt | PR #66 |
| Autopilot-Kern: Telemetrie, vJoy, Regler, Rennlinie | erledigt | PR #67 |
| Systemidentifikation und Kamerakalibrierung in Liftoff | erledigt | PR #67, [Testbericht](../../reports/autonomes-rennen-test) |
| M8: autonome Runde, Rennsieg auf Field Day | erledigt (18.10.2026) | PR #67, [M8](../../../releases/m8-autonome-runde) |
| Zweite Strecke After Hours gewonnen (1:17,035) | erledigt (19.10.2026) | PR #68 |
| M11: Kamera korrigiert falsch eingetragene Tore | erledigt (19.10.2026) | PR #68 |
| GPS-Zielflug in Liftoff mit Hindernissen aus Strecke und Kamera | umgesetzt (26.10.2026) | PR #68 |
| Simulator-CI wieder grün (war seit 26.10. rot: `ctypes.windll` auf Linux, `cv2` fehlte) | erledigt (03.11.2026) | PR #70 |

## Offen

- Zwei Commits auf `feat/tdot-autopilot` sind noch nicht in `main`: TDOT-Challenge mit 5 Bot-Stufen
  und Live-Dashboard, exakte Torgeometrie aus den Liftoff-Prefabs.
- Testreihe GPS-Zielflug in Liftoff (M12: 10 Ziele, 0 Kollisionen).
- M9 (10 Runden bei voller Geschwindigkeit), M10 (Rennmodus mit Bestenliste), Generalprobe und
  Checkliste für den Tag der offenen Tür (Tasks 3.x und 6.x im Change).
- Web-Simulator mit Physik (Change `2026-10-13-phase2-web-simulator`, 1/15 Tasks).
- RC-Modus-Bug in der iOS-App (Change `2026-10-13-fix-ios-rc-mode`, 0/7 Tasks).
- Termine für den Rest von Phase 2 und Datum des Tags der offenen Tür.

## Verknüpft

- [Testbericht autonomes Rennen](../../reports/autonomes-rennen-test)
- [Meilensteine](../../../releases)
- OpenSpec-Change: `openspec/changes/2026-10-14-tdot-autonomes-rennen`
- Pull Requests: #59 – #68, #70, #71
