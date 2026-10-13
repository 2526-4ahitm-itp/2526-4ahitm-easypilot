---
title: OpenSpec-Change anlegen
weight: 9
---

Jede neue Funktion beginnt mit einem Change in `openspec/changes/`.

{{% steps %}}

### Ordner anlegen

```bash
npx @fission-ai/openspec new change 2026-10-20-mein-thema
```

### Proposal schreiben

`proposal.md`: *Why*, *What Changes*, *Capabilities*, *Impact*. Jeder Punkt verweist auf das
Pflichtenheft (`§N.M` in `spec/fsd.md`).

### Delta-Specs schreiben

Unter `specs/<capability>/spec.md` nur die Unterschiede zum aktuellen Stand, als
`## ADDED Requirements`, `## MODIFIED Requirements` oder `## REMOVED Requirements`. Eine
geänderte Requirement komplett wiederholen, mit dem Status nach dem Change.

### Tasks

`tasks.md` mit Checkboxen, `[GAP]` für Code, der eine FSD-Anforderung umsetzt, `[SPEC]` für reine
Spec-Arbeit.

### Validieren

```bash
npx @fission-ai/openspec validate --all
```

### Archivieren

Ist alles umgesetzt:

```bash
npx @fission-ai/openspec archive 2026-10-20-mein-thema
```

Die Deltas wandern in `openspec/specs/`, der Ordner nach `changes/archive/`.

{{% /steps %}}
