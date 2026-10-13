# Handoff: Coaching Runde 1 (Stand 12.10.2026)

Übergabe für die Fortsetzung auf einem anderen Rechner (dort gibt es den LeoCloud-Zugang).
Zuerst diese Datei lesen, dann `plan.md` (Details pro Task) und `tasks.md` (Abhakliste).

## Goal
Alle offenen To-dos aus Coaching Runde 1 (08.10.2026, Phase 2 „Drohnensimulation mit Physik-Engine“ seit 14.09.2026) erledigen: Tests, CI, Doku-Link im README, Projektpräsentation mit Aufgabenstellung/Team/Terminen/Meilensteinen/C4, Deployment auf die LeoCloud.

## Next
1. Offene PRs mergen bzw. prüfen: `chore/mailmap`, `docs/coaching-r1-plan`, `docs/slides-air-unit` (alle gepusht, noch kein PR).
2. AP0 aus `plan.md`: `origin/main` in `ep7-ios-app` mergen, PR nach `main` (der aktuelle iOS-Code liegt nur auf `ep7-ios-app`).
3. AP6 (LeoCloud) zuerst angehen, weil der Zugang auf diesem Rechner ist: Namespace, Host, kubeconfig, Ingress-Vorgaben in `k8s/README.md` festhalten.
4. Danach AP1–AP5 laut `plan.md`, jedes AP als eigener Branch + PR.

## Open / blockers
- iOS-Tests brauchen eine installierte iOS-Plattform + Simulator in Xcode (auf dem Mac fehlte „iOS 26.2“).
- Branch `wip/ep7-local-presentation`: gesicherte, uncommittete Präsentations-Entwürfe vom Mac (pptx, `build_deck*.py`, Logos, `SPEAKER-NOTES.md`). `origin/ep7-ios-app` hat neuere Commits an denselben Dateien → abgleichen, dann Branch löschen oder übernehmen.
- Künftige Termine/Meilensteine Phase 2 und der Wortlaut der Aufgabenstellung Phase 2 fehlen noch (vom Team).
- Welche Physik-Engine der Web-Simulator nutzt, ist offen; C4-Diagramme benennen sie neutral.
- `PlatformIO/Projects/EasyPilotIOS/include/secrets_auto.h` mit echtem WLAN-Passwort ist noch getrackt (AP3); Passwort danach ändern.

<!-- Referenz -->

## Done
- GitHub Pages: Startseite `docs/index.html` (Landing Page), Projektdoku `docs/projektdoku.html`, iOS-Slides `docs/presentation-ios/slides.html` (reveal.js 5.1.0, Design „Mittelding“: dunkelblauer Akzent #0f1b33/#2266d6, Inter). PRs #44–#47 auf `main`.
- Git-Identität vereinheitlicht: `SimonnEder <114646364+SimonnEder@users.noreply.github.com>`; `.mailmap` (Branch `chore/mailmap`) fasst 11 Simon-Identitäten (inkl. `it220234`) und 2 von David zusammen.
- Plan, Proposal, Tasks in diesem Ordner.

## Decisions (with why)
- Phase 2 = **Web-Simulator** (aufbauend auf `webinterface/frontend`, React + three.js). Grund für die Änderung am 14.09.2026: **DJI O4 Air Unit defekt**, kein Video und keine Steuerung über Brille/Fernbedienung, keine Tests mit der echten Drohne.
- Deployment-Ziel **LeoCloud (k8s)** für Backend + Web-Simulator; **Relay bleibt im LAN**, weil er UDP-Broadcasts für die iOS-App sendet.
- Termine/Meilensteine aus dem Repo abgeleitet (Projektstart 07.10.2025, Sprintplanungen 25.11./23.12.2025, Sprint 4 07.05.2026, Sprint 5 23.06.2026); Lücken als „vom Team zu ergänzen“ markieren, nichts erfinden.
- `docs/index.adoc` heißt auf `main` jetzt `docs/projektdoku.adoc` (Pages-Root ist die Landing Page).

## Arbeitsweise (Wünsche von Simon)
- Antworten und Doku auf Deutsch, Code/Kommentare Englisch.
- Ein Branch pro Thema (`<typ>/<thema>` von `origin/main`), Conventional Commits mit deutschem Betreff, ein PR pro Thema; vor Push/Merge fragen.
- Commits **nur als SimonnEder**, **keine** `Co-Authored-By: Claude`/`Claude-Session`-Zeilen, kein „Generated with Claude Code“ in PRs.
- Design der Seiten: nicht nach KI aussehen, aber gestaltet (Mittelding).

## Gefundener Bug
Firmware meldet `"mode":"RC"`, `FlightMode(rawOrIdle:)` macht daraus `.idle` → im Tab „Algorithms“ fehlt der STOP-Button, obwohl Motoren laufen können (`EasyPilotIOS/EasyPilotIOS/ControlView.swift`, `if droneMode != .idle`). Fix in AP7.

## Commands
- iOS-Tests: `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild test -project EasyPilotIOS/EasyPilotIOS.xcodeproj -scheme EasyPilotIOS -destination 'platform=iOS Simulator,name=<iPhone>'`
- Backend: `cd webinterface/backend && ./mvnw test`
- Seiten-Screenshots ohne Chrome: `firefox --headless -no-remote -profile <leerer Ordner> --window-size=1280,720 --screenshot out.png <url>` (ohne eigenes Profil hängt Firefox).
- Pages-Status: `gh api repos/2526-4ahitm-itp/2526-4ahitm-easypilot/pages/builds/latest -q .status`
