---
title: Doku lokal bauen
weight: 8
---

Voraussetzung: [Hugo extended](https://gohugo.io/installation/) ab 0.146 und
[Go](https://go.dev/dl/) (für das Hextra-Modul).

```bash
cd hugo
hugo server
```

Die Seite läuft dann unter `http://localhost:1313/`. Änderungen erscheinen sofort.

## Neue Seiten

- **Sitzungsprotokoll:** `content/de/project/mom/mom_template.md` nach
  `content/de/project/mom/<datum>/index.md` kopieren, `draft: true` entfernen.
- **Sprint-Review:** `content/de/project/sprint-reviews/sprint-review.md` nach
  `content/de/project/sprint-reviews/<datum>_sprint_<n>/index.md` kopieren.
- **Diagramm:** `.puml` nach `content/de/diagrams/` legen und mit
  `{{</* plantuml src="/content/de/diagrams/<name>.puml" /*/>}}` einbinden.
- **Folien:** `content/de/slides/<name>/index.md` mit `type: slides`; Folien werden mit `---`
  getrennt.

Nach dem Merge nach `main` veröffentlicht der Workflow `docs.yml` die Seite auf GitHub Pages.
