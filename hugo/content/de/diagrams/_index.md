---
title: Diagramme
type: docs
weight: 3
---

Alle Diagramme sind PlantUML-Quellen (C4 über die PlantUML-Standardbibliothek) und liegen
neben dieser Seite in `hugo/content/de/diagrams/`. Architekturseite und Präsentation binden
dieselben Dateien ein, Änderungen wirken also überall.

## C4: Systemkontext

Wer benutzt EasyPilot, und mit welchen Systemen spricht es? Die Drohne ist noch drin, aber
ohne Air Unit nicht flugfähig. Für Phase 2 sind Liftoff und die LeoCloud dazugekommen.

{{< plantuml src="c4-kontext.puml" />}}

## C4: Container

Die lauffähigen Teile. Der Web-Simulator ist heute der 3D-Viewer, Physik und Steuerung fehlen
noch ([Change](https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot/tree/main/openspec/changes/2026-10-13-phase2-web-simulator)).

{{< plantuml src="c4-container.puml" />}}

## C4: Komponenten Liftoff-Hover

Der Phase-2-Prototyp, so wie er in `simulator/liftoff-hover/hover.py` umgesetzt ist.

{{< plantuml src="c4-komponenten-liftoff-hover.puml" />}}

## C4: Komponenten Web-Simulator (Ziel)

So soll der Web-Simulator aufgebaut sein. Die Flugmodi werden aus dem Liftoff-Prototyp und dem
iOS-Simulator portiert.

{{< plantuml src="c4-komponenten-web-simulator.puml" />}}

## Deployment

{{< plantuml src="deployment.puml" />}}

## Sequenz: Verbindung und LIVE-Steuerung

{{< plantuml src="sequenz-verbindung.puml" />}}

## Hover-Regelkreis

{{< plantuml src="hover-regelkreis.puml" />}}
