---
title: CI/CD
weight: 8
---

Alle Workflows liegen in `.github/workflows/`. Jeder läuft nur, wenn sich sein Ordner ändert. So
bleibt die CI schnell, und ein Fehler im iOS-Teil blockiert keinen Doku-PR.

| Workflow | Auslöser (Pfade) | Was er tut |
|---|---|---|
| Backend | `webinterface/backend/**` | `./mvnw -B test` mit Java 21 |
| iOS | `EasyPilotIOS/**` | `xcodebuild test` im iOS-Simulator, ohne Signierung |
| Frontend | `webinterface/frontend/**` | `npm ci`, `npm run lint`, `npm run build` |
| Simulator | `simulator/**` | `python -m unittest` für Liftoff-Hover und Autopilot (Rennlinie, Regler, Zielflug) |
| OpenSpec | `openspec/**`, `spec/**` | `openspec validate --all` |
| Images | `webinterface/**` auf `main` | baut und pusht `easypilot-backend` und `easypilot-web` nach ghcr.io |
| Docs | `hugo/**` auf `main` | baut diese Seite und veröffentlicht sie auf GitHub Pages |

## Regeln

- **Keine Secrets für Tests.** Nur der Image-Push nutzt `GITHUB_TOKEN`, und nur auf `main`. Dadurch
  laufen alle Tests auch in Pull Requests.
- **Ein PR pro Thema.** Jeder PR beschreibt Änderung, Warum und Wie getestet.
- **Conventional Commits** mit deutschem Betreff: `feat(sim): …`, `docs(openspec): …`.
