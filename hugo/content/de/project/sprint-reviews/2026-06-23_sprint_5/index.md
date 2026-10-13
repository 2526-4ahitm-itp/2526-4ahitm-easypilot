---
title: 2026-06-23 Sprint 5 (rekonstruiert)
date: 2026-06-23
---

{{< report-card commits="13" prs="4" newlines="3437" remlines="801" modfiles="28" >}}

Zeitraum: 02.06. – 23.06.2026 · rekonstruiert aus Git und OpenSpec am 13.10.2026 · Abschluss Phase 1

## Ziel des Sprints

*Als Pilot möchte ich, dass sich der Simulator im Querformat wie eine echte Flug-App anfühlt und
die Drohne sich nur dann selbst stabilisiert, wenn ich die Sticks loslasse.*

## Umgesetzt

| Aufgabe | Status |
|---|---|
| Querformat: 3D-Szene vollflächig, Joysticks in den Ecken, Einstellungen als Seitenleiste | erledigt |
| Stabilisierung nur ohne Finger auf dem Stick (`isTouching`) | erledigt |
| POSHOLD: Position beim Loslassen merken und zurückfliegen | erledigt |
| Höhenhaltung mit echter PID statt „letztem Gas“ | erledigt |
| Joystick leuchtet grün, solange stabilisiert wird | erledigt |
| OpenSpec auf das ganze Projekt erweitert | erledigt |

## Verknüpft

- OpenSpec: `openspec/changes/archive/2026-06-23-sprint-05`, `…/2026-06-23-sprint-05-landscape-ui`
- Pull Requests: #38, #39, #40, #41
