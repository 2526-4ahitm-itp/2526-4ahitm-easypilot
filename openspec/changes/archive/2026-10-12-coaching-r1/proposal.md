# Proposal: Coaching Runde 1 – Tests, CI, Doku, Präsentation, Deployment

## Context

Am 08.10.2026 gab es das erste Coaching der Phase 2 („Drohnensimulation mit
Physik-Engine“, seit 14.09.2026). Das Feedback bewertet Arbeitsweise, Tests,
Dokumentation, Präsentation und Deployment. Viele Punkte sind rot oder gelb:
keine CI, kein Link zur Doku im README, die Präsentation hat weder
Aufgabenstellung noch Team, Termine, Meilensteine oder C4-Diagramme, und das
Deployment ist nicht beschrieben. Außerdem gibt es außer einem Backend-Test
nur leere Xcode-Test-Templates.

Die Aufgabenstellung hat sich geändert: Phase 1 (Drohnensteuerung) ist
abgeschlossen. Weil die DJI O4 Air Unit der Drohne defekt ist, kann nicht mehr
mit der echten Drohne getestet werden. Phase 2 baut deshalb einen
**Web-Simulator mit Physik-Engine** (aufbauend auf `webinterface/frontend`).

## Goal

Als Team möchten wir alle offenen To-dos aus Coaching Runde 1 abarbeiten, damit
die Ampeln in Runde 2 grün sind und das Projekt nachvollziehbar dokumentiert,
getestet und ausgeliefert ist.

## In Scope

- Automatisierte Tests für die iOS-App (Befehle, Telemetrie, Sound Mode,
  Profile, UI-Smoke-Test) und für den Web-Simulator-Build
- GitHub-Actions-CI für Backend, iOS-App und Frontend
- README: Link zur veröffentlichten Doku, Commit-Konventionen
- Projektdoku: Aufgabenstellung Phase 2 inkl. Änderung mit Datum und Grund,
  Team, Termine, Meilensteine, Tests, bekannte Probleme, Deployment
- Projektpräsentation (reveal.js) mit Aufgabenstellung, Team, aktuellem Stand,
  Terminen, Meilensteinen, C4-Kontext-, -Container- und (Bonus)
  -Komponentendiagramm für die neue Lösung
- Deployment auf die LeoCloud (Kubernetes): Zielsystem, URLs, Deploy-Ablauf
- Eingecheckte WLAN-Zugangsdaten aus dem Repo entfernen
- Einheitliche Git-Identität pro Person (`.mailmap`, erledigt)

## Out of Scope

- Die Implementierung des Web-Simulators selbst (Physik-Engine, Steuerung)
- Firmware-Unit-Tests (PlatformIO fehlt lokal, `main.cpp` müsste zerlegt werden)
- Bereinigen der Git-History von alten Zugangsdaten

## Affected Specs

| Spec | Change type | Notes |
|---|---|---|
| `simulator-controller` | MODIFIED | LIVE-Modus ist implementiert, Spec sagt noch „Available in Sprint 5“ |
| `core` | MODIFIED | Phase 2: Web-Simulator als neues Subsystem, Deployment-Ziel LeoCloud |

## Acceptance Criteria

- [ ] `xcodebuild test` läuft grün mit echten Tests (kein Template mehr)
- [ ] GitHub Actions führt Backend-, iOS- und Frontend-Checks bei jedem Push/PR aus, alle grün
- [ ] README verlinkt https://2526-4ahitm-itp.github.io/2526-4ahitm-easypilot/
- [ ] Projektpräsentation enthält Aufgabenstellung (aktuell + Änderung), Team, Stand, Termine, Meilensteine, C4-Kontext und -Container
- [ ] Projektdoku beschreibt Zielsystem, Produktions-URL und Deploy-Ablauf
- [ ] Backend läuft in der LeoCloud unter der dokumentierten URL
- [ ] `secrets_auto.h` ist nicht mehr getrackt

## Risks / Open Questions

- LeoCloud-Zugang (Namespace, Hostname der Produktions-URL) muss vom Team kommen.
- Welche Physik-Engine der Web-Simulator nutzt, ist noch nicht entschieden;
  die C4-Diagramme benennen sie bis dahin neutral.
- Künftige Projekttermine sind nicht im Repo belegt und kommen vom Team.

## Done When

- Alle Acceptance Criteria sind abgehakt
- Delta-Specs sind in `openspec/specs/` übernommen
- Dieser Ordner ist nach `openspec/changes/archive/` verschoben
