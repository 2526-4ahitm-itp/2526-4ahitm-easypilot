# OpenSpec for EasyPilot

OpenSpec is how the EasyPilot team writes down *what* the system has to do
before *how* it does it. The benefit during a normal sprint: before you
touch code, you and your reviewer can disagree about a sentence in a
spec — much cheaper than disagreeing about a pull request.

This folder is the source of truth. If something here disagrees with the
code, fix one of them; do not let the drift sit.

## Layout

```
openspec/
├── README.md              ← you are here
├── specs/                 ← the always-current contract
│   ├── core/              ← whole-project architecture
│   ├── hardware/          ← ESP32-C3, FC, ESCs, battery
│   ├── firmware/          ← ESP32 flight modes & watchdogs
│   ├── communication/     ← UDP discovery, WebSocket, MSP
│   ├── dashboard/         ← iOS Dashboard tab
│   ├── simulator-controller/  ← iOS Simulator tab + joysticks
│   ├── drone-telemetry/   ← attitude + battery contract
│   └── guidelines.md      ← team workflow rules
├── changes/
│   ├── <YYYY-MM-DD-sprint-NN-name>/   ← active sprint
│   │   ├── proposal.md
│   │   ├── tasks.md
│   │   └── specs/         ← delta specs only — ADD/MODIFY/REMOVE blocks
│   └── archive/           ← completed sprints, kept for history
└── templates/
    ├── sprint-proposal.md
    └── sprint-tasks.md
```

## Workflow for a Normal Sprint

1. **Pick the scope.** Decide which subsystem(s) the sprint touches. Read
   the relevant spec(s) under `specs/` first. If you cannot find your
   feature there, it is either a new capability or a missing spec — both
   are fine, both go in the proposal.

2. **Open a sprint folder.** Copy `templates/sprint-proposal.md` into
   `changes/<YYYY-MM-DD-sprint-NN-name>/proposal.md` and fill in the
   goal + acceptance criteria. Copy `templates/sprint-tasks.md` into
   `tasks.md` and break the work into checkbox phases.

3. **Write the delta specs.** Under
   `changes/<sprint>/specs/<capability>/spec.md`, only describe what
   *changes* relative to the live spec. Use the headings:
   - `## ADDED Requirements` — brand-new requirements
   - `## MODIFIED Requirements` — existing ones whose behaviour changes
   - `## REMOVED Requirements` — things being deleted (rare; explain why)

4. **Implement.** Code against the proposal. Tick boxes in `tasks.md` as
   you go. If you have to deviate, update the proposal/spec *before*
   merging — the spec is a promise, not a wish.

5. **Archive.** When the sprint is done:
   - Fold the delta specs into the live ones under `specs/`
   - `git mv changes/<sprint> changes/archive/<sprint>`
   - Commit with a message that names the sprint

## Authoring Rules of Thumb

- **Requirement format.** Each `### Requirement: …` is a single SHALL
  statement. Long descriptions go after the heading. Every requirement
  has at least one `#### Scenario:` block with `Given / When / Then`.
- **Be testable.** If the scenario cannot be reduced to a manual or
  automated check, rewrite it until it can.
- **Be terse.** Specs decay if they are tedious to read. Aim for the
  shortest text that still answers "what does the system promise to do?"
- **One source of truth.** When the spec moves, the README and `CLAUDE.md`
  references should move with it. Do not duplicate behavioural rules
  across multiple docs.

## When *Not* to Open an OpenSpec Change

- Pure bugfixes that restore documented behaviour. Just file the bug,
  fix the code, link them in the commit.
- Refactors that do not change the external contract.
- Doc-only typo fixes.

If in doubt, write the proposal anyway — it takes 10 minutes and saves
the reviewer 30.

## Cross-References

- Team workflow rules: [`specs/guidelines.md`](specs/guidelines.md)
- Build & deploy instructions: `CLAUDE.md` at the repo root
- Active sprint: `changes/2026-06-23-sprint-05-landscape-ui/`
