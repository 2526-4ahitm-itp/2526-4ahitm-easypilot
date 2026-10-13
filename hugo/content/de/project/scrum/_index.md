---
title: Scrum und Team
weight: 1
---

## Team

| Person | Schwerpunkte laut Git-History (Stand 13.10.2026) |
|---|---|
| Simon Eder | iOS-App, beide Firmwares, OpenSpec, CI, Kubernetes-Manifeste, Pages |
| David Windischbauer | Web-Viewer (React/three.js), Backend und Python-Skripte, MAVLink-/Motortests (Sprint 1–2), Liftoff-Hover (Phase 2), Hugo-Doku und OpenSpec-Neuaufbau |

Rollen wie Scrum Master und Product Owner werden im Zweierteam abwechselnd wahrgenommen:
*vom Team zu ergänzen*.

## Arbeitsweise

- **Sprints:** in Phase 1 zwei bis vier Wochen. Jeder Sprint hat eine Planung mit User Story und
  Definition of Done ([Protokolle](../mom)) und ein Review ([Sprint-Reviews](../sprint-reviews)).
- **Anforderungen:** seit 24.03.2026 in OpenSpec. Jede Änderung ist ein Change mit Proposal, Tasks
  und Delta-Specs.
- **Git:** ein Branch pro Thema (`<typ>/<thema>`), Conventional Commits mit deutschem Betreff, ein
  Pull Request pro Thema mit „Änderung / Warum / Wie getestet“.
- **Identitäten:** `.mailmap` fasst alle Git-Identitäten pro Person zusammen, damit
  `git shortlog -sn` die Verteilung im Team richtig zeigt.
