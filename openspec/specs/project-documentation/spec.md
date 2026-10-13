## Purpose

How EasyPilot is documented and presented: a Hugo site structured after Diátaxis plus a project area with meeting minutes, sprint reviews and reports, slides, diagrams and milestones, published on GitHub Pages and linked from the README (FSD §14, US-10). The structure follows the Franklyn project of the same class.

## Requirements

### Requirement: Hugo documentation site

The documentation SHALL be a Hugo site with the Hextra theme in `hugo/`, in German, with the sections `docs` (Erklärung, Anleitungen, Referenz), `project` (Sitzungsprotokolle, Sprint-Reviews, Berichte, Scrum), `diagrams`, `releases` (milestones), `guide` and `slides` (§14).

`status: implemented`

#### Scenario: Local build
- **WHEN** `hugo --minify` runs in `hugo/`
- **THEN** the site builds without errors

### Requirement: Published on GitHub Pages

A workflow SHALL build the Hugo site on every push to `main` that changes `hugo/` and deploy it to GitHub Pages; the README SHALL link to it (§14, US-10).

`status: partial`

#### Scenario: Merge to main
- **WHEN** a change under `hugo/` is merged
- **THEN** the new site is live on `https://2526-4ahitm-itp.github.io/2526-4ahitm-easypilot/` (partial: requires the Pages source to be switched to „GitHub Actions“ in the repository settings)

### Requirement: Project presentation

The site SHALL contain a project presentation with task, change of task (date and reason), team, current state, dates, milestones and C4 context, container and component diagrams of the current solution (§14, US-10).

`status: implemented`

#### Scenario: Presentation opened
- **WHEN** `/slides/projektstand/` is opened
- **THEN** all listed topics and the C4 diagrams are shown

### Requirement: Meeting minutes and sprint reviews

Every sprint planning and review SHALL be recorded as a page under `project/mom` or `project/sprint-reviews` using the provided templates (§14).

`status: partial`

#### Scenario: New sprint
- **WHEN** a sprint ends
- **THEN** a sprint review page exists (partial: minutes exist for 2025-11-25 and 2025-12-23 only; reviews for sprints 3–5 were reconstructed from OpenSpec)

### Requirement: Conventional commits and one PR per topic

Work SHALL happen on one branch per topic (`<type>/<topic>`), with Conventional Commits and German subjects, merged through a pull request (§14).

`status: implemented`

#### Scenario: Commit message
- **WHEN** a commit is created
- **THEN** its subject follows `<type>(<scope>): <German imperative>`
