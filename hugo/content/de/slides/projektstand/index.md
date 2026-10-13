---
title: "Projektstand"
date: 2026-10-13
layout: single
type: slides
watermark: EasyPilot
---

{{< front title="EasyPilot" subtitle="Projektstand · Phase 2" author="Simon Eder · David Windischbauer · 4AHITM 2025/26" >}}

---

## Team

{{< twocol >}}
{{< col >}}
### Simon Eder
iOS-App · Firmware · OpenSpec · CI · Deployment
{{< /col >}}
{{< col >}}
### David Windischbauer
Web-Viewer · Backend/Python · Liftoff-Hover · Doku
{{< /col >}}
{{< /twocol >}}

---

## Aufgabenstellung

**Phase 2 (seit 14.09.2026): Drohnensimulation mit Physik-Engine**

{{% slide-steps %}}

Flugverhalten, Steuerung und Assistenzfunktionen **ohne Hardware** entwickeln, testen, vorführen.

**Liftoff-Hover:** Autopilot auf dem FPV-Simulator Liftoff – Prototyp, fertig.

**Web-Simulator:** Physik im Browser, aus der LeoCloud – in Arbeit.

{{% /slide-steps %}}

---

## Änderung der Aufgabenstellung

| Datum | Änderung | Grund |
|---|---|---|
| 14.09.2026 | Phase 1 „Drohnensteuerung“ → Phase 2 „Drohnensimulation mit Physik-Engine“ | **DJI O4 Air Unit defekt:** kein Bild, keine Steuerung über Brille/Fernbedienung, keine Flugtests |

---

## Aktueller Stand

{{< stats >}}
{{< stat value="74" label="Anforderungen umgesetzt" color="success" >}}
{{< stat value="9" label="teilweise" color="warning" >}}
{{< stat value="12" label="offen" color="error" >}}
{{< /stats >}}

Phase 1 fertig: Firmware, iOS-App, Relay, Web-Viewer · Phase 2: Liftoff-Hover fertig, Web-Simulator offen

---

## Liftoff-Hover: gemessen

{{% slide-steps %}}

Hover im Steigflug mit **16 m/s** eingeschaltet

nach **~2 s** abgebremst, nach **~5 s** steht die Drohne auf 57,43 m

danach **keine messbare Drift** – Regler-Tests laufen in CI

{{% /slide-steps %}}

---

## Projekttermine

| Datum | Ereignis |
|---|---|
| 07.10.2025 | Projektstart |
| 25.11. / 23.12.2025 | Sprintplanungen 1 und 2 |
| 24.03.2026 | OpenSpec, Sprint 3 |
| 07.05. – 23.06.2026 | Sprint 4 und 5, Ende Phase 1 |
| 14.09.2026 | Start Phase 2 |
| 28.09.2026 | Liftoff-Hover getestet |
| 08.10.2026 | Coaching Runde 1 |
| *vom Team zu ergänzen* | weitere Termine Phase 2 |

---

## Meilensteine

| | | |
|---|---|---|
| M1 | Live-Telemetrie im 3D-Modell | ✓ |
| M2 | Motoren einzeln ansteuern | ✓ |
| M3 | MSP-Telemetrie, hybride Verbindung | ✓ |
| M4 | Simulator in der iOS-App, LIVE | ✓ |
| M5 | Landscape, POSHOLD – Ende Phase 1 | ✓ |
| M6 | Hover-Prototyp in Liftoff | ✓ |
| M7 | Web-Simulator in der LeoCloud | offen |

---

## C4: Systemkontext

{{% center %}}
{{< plantuml src="/content/de/diagrams/c4-kontext.puml" />}}
{{% /center %}}

---

## C4: Container

{{% center %}}
{{< plantuml src="/content/de/diagrams/c4-container.puml" />}}
{{% /center %}}

---

## C4: Komponenten Liftoff-Hover

{{% center %}}
{{< plantuml src="/content/de/diagrams/c4-komponenten-liftoff-hover.puml" />}}
{{% /center %}}

---

## C4: Komponenten Web-Simulator (Ziel)

{{% center %}}
{{< plantuml src="/content/de/diagrams/c4-komponenten-web-simulator.puml" />}}
{{% /center %}}

---

## Deployment

{{% slide-steps %}}

**LeoCloud:** Web-Simulator `/` und Backend `/api` auf `it220270.cloud.htl-leonding.ac.at` – **live** seit 14.10.2026

**ghcr.io:** Images aus GitHub Actions bei jedem Merge

**GitHub Pages:** diese Doku und Präsentation

**Bleibt lokal:** Relay (UDP im LAN), Liftoff-Hover (Windows + Liftoff)

{{% /slide-steps %}}

---

## Tests & CI

| Workflow | prüft |
|---|---|
| iOS | Befehlsformat, Telemetrie, Sound Mode, Profile, UI-Smoke-Test |
| Backend | `GET /api/status` |
| Frontend | Lint, Build |
| Simulator | Hover-Regler im geschlossenen Kreis |
| OpenSpec | alle Specs und Changes valide |

---

## Nächste Schritte

{{% slide-steps %}}

Physik-Modul und Steuerung für den Web-Simulator

Hover aus dem Liftoff-Prototyp in den Web-Simulator portieren

RC-Modus-Bug in der App beheben

{{% /slide-steps %}}

---

{{< front title="Danke!" subtitle="Fragen?" >}}
