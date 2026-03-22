# Tasks: GHA CI/CD Pipeline

**Input**: Design documents from `/specs/003-gha-cicd-pipeline/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Evals**: Per the project constitution, evals are NON-NEGOTIABLE. Every user story phase includes eval tasks. All evals MUST pass before the feature is complete.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup

**Purpose**: Create directory structure, clean up versioning, and add release-please config files before any CI logic is added.

- [ ] T001 Create `.github/workflows/` and `.github/scripts/` directories in repo root
- [ ] T002 Remove `version` field from `.claude-plugin/marketplace.json` (FR-012)
- [ ] T003 [P] Create `release-please-config.json` at repo root: `release-type: simple`, `packages` entry for `.` with `extra-files` pointing `$.version` jsonpath at `.claude-plugin/plugin.json` (FR-008)
- [ ] T004 [P] Create `.release-please-manifest.json` at repo root with `{ ".": "1.0.1" }` matching current `plugin.json` version (FR-009)
- [ ] T005 [P] Create `CONTRIBUTING.md` at repo root — conventional commit types, which types trigger a release vs not, branch naming, local validation steps, PR and release process, and agent-specific commit guidance (FR-014)

---

## Phase 2: Foundational (Blocking Prerequisite)

**Purpose**: `validate.sh` is the shared core used by both the GHA validate job (US1) and local developer workflow (US3). Must exist before either story can be implemented.

**⚠️ CRITICAL**: US1 and US3 both depend on this phase completing first.

- [ ] T005 Create `.github/scripts/validate.sh` — bash script with `set -e`, three sequential steps: `python3 -m py_compile scripts/generate_report.py`, SKILL.md frontmatter check (grep for `---` block containing `name:` and `description:` — uses `${SKILL_MD:-./SKILL.md}` env var so tests can override the path), and `python3 -m unittest discover -s evals -p "test_*.py" -v`. Each passing step prints `[OK] <check name>`. Make executable with `chmod +x`.

**Checkpoint**: T003/T004 config files exist and are valid JSON. T005 `validate.sh` passes on a clean checkout before proceeding.

---

## Phase 3: User Story 1 — PR Contributor Gets Fast Feedback (Priority: P1) 🎯 MVP

**Goal**: Every PR to main automatically runs validation and blocks merge on failure.

**Independent Test**: Open a PR with a syntax error in `scripts/generate_report.py` → validate job fails. Fix it → validate job passes.

### Implementation for User Story 1

- [ ] T006 [US1] Create `.github/workflows/ci.yml` with `validate` job: trigger on `pull_request` and `push` to `main`, runs on `ubuntu-24.04`, sets up Python 3.10 via `actions/setup-python@v5`, then invokes `.github/scripts/validate.sh` as a single step

### Evals for User Story 1

- [ ] T007 [P] [US1] Create `evals/test_ci_validate.py` — EVAL-001: introduce a syntax error into a temp copy of `scripts/generate_report.py`, run `.github/scripts/validate.sh`, assert exit code is non-zero and stderr/stdout contains the filename
- [ ] T008 [US1] Add EVAL-002 to `evals/test_ci_validate.py` — write a temp `SKILL.md` missing the `name:` field to a tempfile, set `SKILL_MD=<tempfile>` env var, run `.github/scripts/validate.sh`, assert exit code non-zero and output identifies the missing field
- [ ] T009 [US1] Add EVAL-003 to `evals/test_ci_validate.py` — run `.github/scripts/validate.sh` on the real repo with no modifications, assert exit code is 0 and output contains three `[OK]` lines
- [ ] T010 [US1] Run `python3 -m unittest evals/test_ci_validate.py -v` and confirm EVAL-001, EVAL-002, EVAL-003 all pass

**Checkpoint**: US1 fully functional — validate job exists, local script works, all three evals pass.

---

## Phase 4: User Story 2 — Merge to Main Produces a Tagged Release (Priority: P1)

**Goal**: Every merge to main that passes validation auto-bumps the version, tags it, and publishes a GitHub Release.

**Independent Test**: Merge a clean `fix:` PR to main at version `1.0.1` → `plugin.json` updates to `1.0.2`, tag `v1.0.2` exists, GitHub Release published — no manual steps.

### Implementation for User Story 2

- [ ] T011 [US2] Add `release` job to `.github/workflows/ci.yml`: `needs: validate`, `if: github.event_name == 'push'`, `permissions: contents: write, pull-requests: write`, single step using `googleapis/release-please-action@v4` with `token: ${{ secrets.GITHUB_TOKEN }}`, `config-file: release-please-config.json`, `manifest-file: .release-please-manifest.json`

### Evals for User Story 2

- [ ] T012 [US2] Create `evals/test_release_config.py` — EVAL-004: parse `release-please-config.json` and `.release-please-manifest.json`, assert both are valid JSON, config has `release-type: simple` and an extra-files entry with `path: .claude-plugin/plugin.json` and `jsonpath: $.version`, and the version in manifest matches the version in `plugin.json`
- [ ] T013 [US2] Run `python3 -m unittest evals/test_release_config.py -v` and confirm EVAL-004 passes

**Checkpoint**: US2 fully functional — release job wired up with release-please, config files valid and in sync, EVAL-004 passes.

---

## Phase 5: User Story 3 — Developer Validates Locally (Priority: P2)

**Goal**: Contributors can run `.github/scripts/validate.sh` locally and get the same result as CI.

**Independent Test**: Run `.github/scripts/validate.sh` on a clean checkout → exit 0. Introduce a syntax error → exit non-zero with clear error.

### Implementation for User Story 3

- [ ] T014 [US3] Confirm `.github/scripts/validate.sh` is committed as executable (verify `git ls-files --stage .github/scripts/validate.sh` shows mode `100755`)

### Evals for User Story 3

- [ ] T015 [US3] Add EVAL-005 to `evals/test_ci_validate.py` — run `.github/scripts/validate.sh` as a subprocess from the repo root on an unmodified checkout, assert exit code 0 and output contains `[OK] Python syntax check`, `[OK] SKILL.md frontmatter`, `[OK] Evals`
- [ ] T016 [US3] Run `python3 -m unittest evals/test_ci_validate.py -v` and confirm EVAL-005 passes alongside EVAL-001/002/003

**Checkpoint**: US3 complete — local validate script works identically to CI for any contributor.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T017 Run the full eval suite `python3 -m unittest discover -s evals -p "test_*.py" -v` and confirm zero failures across all evals (EVAL-001 through EVAL-005)
- [ ] T018 Update `TODO.md` — mark CI pipeline tasks complete
- [ ] T019 [P] Validate `quickstart.md` steps end-to-end: run `.github/scripts/validate.sh`, confirm output matches documented format

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately; T003 and T004 can run in parallel
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS US1 and US3
- **US1 (Phase 3)**: Depends on Phase 2 (validate.sh must exist)
- **US2 (Phase 4)**: Depends on Phase 3 (ci.yml must exist to add release job); T012/T013 can start once T003/T004 are done
- **US3 (Phase 5)**: Depends on Phase 2 (validate.sh must exist); can run in parallel with US2
- **Polish (Phase 6)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Blocked only by Foundational phase
- **US2 (P1)**: Blocked by US1 (adds to ci.yml created in US1); release-please config eval (T012/T013) can start earlier
- **US3 (P2)**: Blocked only by Foundational phase — can run in parallel with US1/US2

### Parallel Opportunities

- T003, T004 (Setup) can run in parallel — different files
- T007 creates `test_ci_validate.py`; T008 must follow sequentially (adds to same file)
- T012/T013 (US2 release config eval) can run once T003/T004 exist — independent of ci.yml
- US3 (T014–T016) can proceed in parallel with US2 once Foundational is done
- T018, T019 (Polish) can run in parallel

---

## Parallel Example: Setup Phase

```bash
# T003 and T004 can be created simultaneously — independent files:
Task T003: release-please-config.json
Task T004: .release-please-manifest.json
```

---

## Implementation Strategy

### MVP (US1 Only)

1. Phase 1: Setup (T001–T004)
2. Phase 2: Foundational (T005) — validate.sh
3. Phase 3: US1 (T006–T010) — ci.yml validate job + evals
4. **STOP and VALIDATE**: PRs are now gated. Merge blocker is live.

### Incremental Delivery

1. Setup + Foundational → config files + validate.sh ready
2. US1 → validate job live on PRs (MVP gate)
3. US2 → release-please wired up; merges now open Release PRs automatically
4. US3 → confirmed local dev parity
5. Polish → full suite green

---

## Notes

- `validate.sh` is the shared foundation — get it right in Phase 2 before building US1 or US3 on top
- US2 adds the `release` job to the ci.yml created in US1 — do not create a separate file
- release-please manages its own loop prevention — no `[skip ci]` needed
- The release-please manifest version must always match `plugin.json` version — keep them in sync
- After implementation is merged, manually configure branch protection on `main` to require the `validate` status check (see quickstart.md)
