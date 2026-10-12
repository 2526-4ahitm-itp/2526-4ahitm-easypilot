# Tasks: Coaching Runde 1

Details zu jedem Punkt: `plan.md` in diesem Ordner.

## Status Tracking
- [x] Plan und Proposal
- [x] Handoff für Rechnerwechsel (`handoff.md`)
- [x] `.mailmap`, einheitliche Git-Identität (`chore/mailmap`)
- [x] AP0: iOS-Stand nach `main` (`ep7-ios-app`) – #51 gemergt
- [ ] AP1: iOS-Tests (`test/ios-unit-tests`) – PR #52
- [ ] AP2: CI mit GitHub Actions (`ci/github-actions`) – PR #53
- [ ] AP3: Zugangsdaten und Experimente (`chore/firmware-secrets`) – PR #54
- [ ] AP4: Doku (`docs/coaching-r1`) – PR #55
- [ ] AP5: Projektpräsentation (`docs/project-presentation`) – PR #56
- [ ] AP6: Deployment LeoCloud (`feat/k8s-leocloud`) – PR #57, vorbereitet, nicht deployt
- [ ] AP7 (optional): RC-Modus (`fix/ios-rc-mode`)

## Offene To-dos aus dem Coaching

- [ ] Automatisierte Tests ergänzen → AP1, AP2
- [ ] Tests in CI ausführen → AP2
- [ ] Link zur veröffentlichten Doku im README ergänzen → AP4
- [ ] Präsentation (reveal.js) mit Aufgabenstellung, Team, aktuellem Stand, Terminen, Meilensteinen, C4-Kontext und -Container → AP5
- [ ] Änderung der Aufgabenstellung mit Datum und Grund dokumentieren → AP4 (Task 4.4), AP5
- [ ] C4-Diagramme auf „Drohnensimulation mit Physik-Engine“ aktualisieren → AP5
- [ ] Zielsystem für den Betrieb (Backend, Relay) in der Doku beschreiben → AP6
- [ ] Produktions-URL in der Doku angeben → AP6
- [ ] Deploy-Ablauf (Build, Auslieferung, Start) dokumentieren → AP6

## Vorbedingungen vom Team
- [x] iOS-Plattform in Xcode installiert (Mac mit Xcode 26.3, iOS-26.3-Simulator)
- [x] Lokale Änderungen auf `ep7-ios-app` committet oder verworfen (gesichert auf lokalem Branch `wip/ep7-test-mode`)
- [x] LeoCloud: Namespace, Host, kubeconfig, Ingress-Vorgaben (`student-it220234`, `it220234.cloud.htl-leonding.ac.at`, Ingress-Klasse `nginx`)
- [ ] Künftige Termine und Meilensteine Phase 2
- [ ] Wortlaut Aufgabenstellung Phase 2 bestätigt
- [ ] WLAN-Passwort geändert (nach AP3)
