---
title: Dokumentation
description: Die gesamte technische Dokumentation von EasyPilot
---

Die Doku folgt [Diátaxis](./diataxis): Jede Seite beantwortet genau eine Art von Frage.

## Wo anfangen?

- [Erklärung](./explanation): *Warum* ist EasyPilot so gebaut? Architektur, Phase 2, Kommunikation, Regler.
- [Anleitungen](./how-to-guides): *Wie* mache ich X? Firmware flashen, App installieren, deployen, testen.
- [Referenz](./reference): *Was genau* gilt? Befehle, Telemetrie, MSP, Ports, Hardware, Spec-Status.

Wer EasyPilot nur benutzen will, findet das in der [Anleitung](../guide).

## Stand

| | |
|---|---|
| Phase | **2: Drohnensimulation mit Physik-Engine** (seit 14.09.2026) |
| Grund | DJI O4 Air Unit defekt, die echte Drohne fliegt nicht mehr ([Bericht](../project/reports/air-unit-defekt)) |
| Fertig | Firmware, iOS-App, Relay, Web-Viewer (Phase 1); Liftoff-Hover-Prototyp (Phase 2) |
| Offen | Web-Simulator mit Physik, Deployment in die LeoCloud |

Was genau umgesetzt ist, steht pro Anforderung in der [Spec-Übersicht](./reference/openspec).

## Quellen der Wahrheit

- **Pflichtenheft:** [`spec/fsd.md`](https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot/blob/main/spec/fsd.md)
- **Anforderungen mit Status:** [`openspec/specs/`](https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot/tree/main/openspec/specs)
- **Code:** [GitHub](https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot)
