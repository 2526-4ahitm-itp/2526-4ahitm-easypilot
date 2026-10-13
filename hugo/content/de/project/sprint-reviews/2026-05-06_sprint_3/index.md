---
title: 2026-05-06 Sprint 3 (rekonstruiert)
date: 2026-05-06
---

{{< report-card commits="17" prs="5" modfiles="7832" >}}

Zeitraum: 24.03. – 06.05.2026 · rekonstruiert aus Git und OpenSpec am 13.10.2026

Die Zeilenzahlen fehlen bewusst. In diesem Zeitraum wurde ein `node_modules`-Ordner eingecheckt
und wieder entfernt, was die Statistik auf ±3,7 Mio. Zeilen verfälscht.

## Ziel des Sprints

*Als Entwickler möchte ich die Bewegungssensoren des iPhones sicher nutzen und eine Verbindung
haben, die lokal (direkt) und remote (Ngrok) ohne Codeänderung funktioniert. Außerdem will ich die
App schneller auf das iPhone bringen.*

## Umgesetzt

| Aufgabe | Status |
|---|---|
| Umstieg auf OpenSpec (PR #31) | erledigt |
| iPhone-Neigung in der App anzeigen | erledigt |
| Safe-Test-Modus (M1 kurz auf 1050) statt Flugsteuerung per Neigung | erledigt |
| Hybride Verbindung: lokal per Beacon/WebSocket, remote über Relay und Ngrok | erledigt |
| Ein-Klick-Deploy `deploy.sh` | erledigt |
| Backend-Tests (PR #33) | erledigt |

## Verknüpft

- OpenSpec: `openspec/changes/archive/2026-05-28-sprint-03`
- Pull Requests: #30, #31, #33, #34, #35
