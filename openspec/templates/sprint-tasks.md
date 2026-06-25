# Tasks: Sprint NN - <Short Name>

> Copy this file to `openspec/changes/<YYYY-MM-DD-sprint-NN-name>/tasks.md`.
> Replace `<…>` placeholders and delete this blockquote.

## Status Tracking
- [ ] Phase 1: Spec & design
- [ ] Phase 2: Implementation
- [ ] Phase 3: Test on hardware / device
- [ ] Phase 4: Docs & archive

---

## Detailed Task List

### Phase 1: Spec & design
- [ ] Write `proposal.md` (use `templates/sprint-proposal.md`)
- [ ] Write delta spec(s) under `specs/<capability>/spec.md`
- [ ] Review proposal with handler

### Phase 2: Implementation
- [ ] <Concrete task 1 — file/function level if possible>
- [ ] <Concrete task 2>
- [ ] <…>

### Phase 3: Test on hardware / device
- [ ] Build firmware (`pio run`) and flash to ESP32
- [ ] Build iOS app (`./deploy.sh` or the xcodebuild command in `CLAUDE.md`)
- [ ] Verify each acceptance criterion from the proposal
- [ ] Run a regression check on the previous sprint's headline feature

### Phase 4: Docs & archive
- [ ] Fold delta spec(s) into `openspec/specs/`
- [ ] Update `CLAUDE.md` if any architecture-level fact changed
- [ ] `git mv openspec/changes/<sprint> openspec/changes/archive/<sprint>`
- [ ] Commit (no push without handler approval)
