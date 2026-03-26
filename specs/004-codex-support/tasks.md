# Tasks: Codex Platform Support

**Input**: Design documents from `/specs/004-codex-support/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Evals**: Per the project constitution, evals are NON-NEGOTIABLE. Every user story phase MUST include an eval task. All evals MUST pass before the feature is complete.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are listed in every task

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Minimal changes to existing shared data structures and CLI wiring needed before any user story work begins.

- [ ] T001 Add `codex_source: Optional[str] = None` field to `Session` dataclass in `skills/myusage/scripts/generate_report.py`
- [ ] T002 Add `--codex-dir` CLI argument (default `~/.codex/`) to the `argparse` block in `main()` in `skills/myusage/scripts/generate_report.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Eval fixture rollout JSONL files that all three user story eval phases depend on. These are plain-text files committed to the repo; no binary SQLite needed (the test suite constructs the database in setUp()).

**⚠️ CRITICAL**: Eval tests for every user story read from these fixtures. No user story eval can run until this phase is complete.

- [ ] T003 [P] Create `evals/fixtures/codex/rollouts/session-codex-001.jsonl` — `turn_context` line (model omitted — model set in DB row), 2 `response_item` user lines with category keyword "debug"; no `event_msg user_message` line needed (first_user_message comes from DB)
- [ ] T004 [P] Create `evals/fixtures/codex/rollouts/session-codex-002.jsonl` — `turn_context` line with `"model": "o3"` (DB model=NULL for this session), 3 `response_item` user lines with category keyword "implement"
- [ ] T005 [P] Create `evals/fixtures/codex/rollouts/session-codex-003.jsonl` — `turn_context` line (model explicit), 1 `response_item` user line with category keyword "explain"; session has `source="vscode"` in DB

**Checkpoint**: Fixture files committed — eval tests for all user stories can now be written.

---

## Phase 3: User Story 1 — Codex Sessions in Usage Report (Priority: P1) 🎯 MVP

**Goal**: Parse all Codex sessions from the local SQLite database and include them in the generated report alongside Claude Code and Copilot sessions. Handle missing database gracefully.

**Independent Test (EVAL-001)**: Given `evals/fixtures/codex/` with 3 synthetic sessions, run the report generator and verify: (a) report contains a Codex platform entry, (b) session count = 3, (c) token totals match fixture data, (d) model names are correctly resolved.

**Independent Test (EVAL-002)**: Given no Codex database present (`--codex-dir /nonexistent/`), verify script exits 0 and produces a valid report for other platforms.

### Implementation for User Story 1

- [ ] T006 [US1] Implement `_find_codex_db(codex_dir: str) -> Optional[str]` helper (glob `state_*.sqlite`, pick highest N) in `skills/myusage/scripts/generate_report.py`
- [ ] T007 [US1] Implement `parse_codex(codex_dir: str) -> List[Session]` — DB discovery via `_find_codex_db()`, `sqlite3` read-only query of `threads` table (columns: `id`, `rollout_path`, `created_at`, `updated_at`, `source`, `cwd`, `tokens_used`, `first_user_message`, `model`, `approval_mode`; skip rows where `archived=1`), Session construction (tool=`"codex"`, `input_tokens=tokens_used`, `output_tokens=None`, `codex_source` from `source` column, `mode` from `approval_mode`), rollout JSONL parsing for (1) model resolution when DB `model` IS NULL via `turn_context` line and (2) user `response_item` message counting via `_is_system_message()`, `first_user_message` from DB used directly for `categorize_session()` (no rollout read for this), `classify_session_character()` + `categorize_session()` calls — in `skills/myusage/scripts/generate_report.py`
- [ ] T008 [US1] Add Codex exclusion guard to `compute_session_costs()` — Codex sessions (tool=`"codex"`) MUST have `estimated_cost_usd = None` and `effective_prus = None` — in `skills/myusage/scripts/generate_report.py`
- [ ] T009 [US1] Integrate `parse_codex(args.codex_dir)` call in `main()` alongside `parse_claude_code`, `parse_copilot_vscode`, `parse_copilot_cli` in `skills/myusage/scripts/generate_report.py`
- [ ] T010 [P] [US1] Create `evals/test_codex_missing.py` — EVAL-002: assert `parse_codex("/nonexistent/")` returns `[]`; assert full report run with `--codex-dir /nonexistent/` exits 0
- [ ] T011 [US1] Create `evals/test_codex_parse.py` — EVAL-001: construct fixture `state_5.sqlite` DB in `setUp()` using the verified schema (all NOT NULL columns required: `id`, `rollout_path`, `created_at`, `updated_at`, `source`, `model_provider`, `cwd`, `title`, `sandbox_policy`, `approval_mode`, plus `tokens_used`, `has_user_event`, `archived`, `first_user_message`, and nullable `model`); call `parse_codex(fixture_dir)`; assert session count=3, assert token totals match fixture values, assert model names resolved correctly for sessions with and without DB-level model

**Checkpoint**: US1 complete — `parse_codex()` works end-to-end, Codex sessions appear in the generated report, no-DB path is safe.

---

## Phase 4: User Story 2 — Codex Session Detail & Categorization (Priority: P2)

**Goal**: Codex sessions are assigned to meaningful categories and session characters using the same keyword-matching logic as Claude Code and Copilot sessions. Per-session detail shows `codex_source`.

**Independent Test (EVAL-003)**: Given fixture sessions with first user messages covering at least 3 category keywords (debug, implement, explain), verify each session is assigned the expected category.

**Independent Test (EVAL-004)**: Given a fixture session with NULL model in the thread record and a valid `turn_context` event in its rollout file (`session-codex-002.jsonl`), verify `session.model == "o3"`.

### Implementation for User Story 2

- [ ] T012 [US2] Verify `parse_codex()` uses `first_user_message` from the `threads` DB row to construct a synthetic `Message` for `categorize_session()` — this column is directly available (migration 0007, NOT NULL with default `''`); no rollout JSONL read needed for categorization. Confirm `session.messages` list is populated with user-role `response_item` `Message` objects from rollout JSONL for `message_count` only — in `skills/myusage/scripts/generate_report.py`
- [ ] T013 [US2] Extend `evals/test_codex_parse.py` — EVAL-003: assert session-codex-001 category contains "Debug", session-codex-002 category matches "Code Generation" (or equivalent for "implement"), session-codex-003 category matches expected keyword for "explain"
- [ ] T014 [US2] Extend `evals/test_codex_parse.py` — EVAL-004: assert session-codex-002 `session.model == "o3"` (resolved from rollout `turn_context`, not from DB where model is NULL)

**Checkpoint**: US2 complete — Codex sessions have correct categories and session characters; NULL model resolved from rollout JSONL.

---

## Phase 5: User Story 3 — Codex Data in Cross-Platform Comparisons (Priority: P3)

**Goal**: Codex appears as a distinct entry in the platform breakdown chart alongside Claude Code, Copilot CLI, and Copilot VS Code. Cost cells for Codex display `—` with a footnote. Activity timeline includes Codex sessions in correct date slots.

**Independent Test (EVAL-005)**: Given fixtures for all 4 platforms (`claude_code`, `copilot_cli`, `copilot_vscode`, `codex`), run the report generator and verify the platform breakdown section includes a distinct Codex entry with correct aggregate token values.

### Implementation for User Story 3

- [ ] T015 [US3] Update HTML renderer in `render_html()` to display `—` for Codex cost cells (check `session.tool == "codex"` or `output_tokens is None` on Codex sessions) in `skills/myusage/scripts/generate_report.py`
- [ ] T016 [US3] Add Codex cost footnote to the generated HTML report (FR-012: "Codex cost unavailable — session database provides only a combined token total with no input/output breakdown") in `skills/myusage/scripts/generate_report.py`
- [ ] T017 [US3] Create `evals/test_codex_report.py` — EVAL-005: run report generator with all 4 fixture directories (`--claude-dir`, `--vscode-dir`, `--copilot-cli-dir`, `--codex-dir`); assert HTML contains a Codex platform entry; assert aggregate Codex token total matches sum of fixture `tokens_used` values

**Checkpoint**: US3 complete — Codex appears in all cross-platform charts; cost display shows `—` with footnote.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Regression validation and documentation.

- [ ] T018 Run full eval suite `python -m unittest discover -s evals -p "test_*.py"` and confirm all 5 new Codex evals pass and all 54 existing evals continue to pass (zero regressions)
- [ ] T019 [P] Update `skills/myusage/SKILL.md` or `README.md` to list Codex as a supported data source alongside Claude Code and Copilot

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (Session field must exist) — BLOCKS all user story evals
- **US1 (Phase 3)**: Depends on Phase 1 + Phase 2 — provides the `parse_codex()` function all other phases build on
- **US2 (Phase 4)**: Depends on US1 (parse_codex must exist and populate `messages`)
- **US3 (Phase 5)**: Depends on US1 (Codex sessions must flow through `build_report()`)
- **Polish (Phase 6)**: Depends on US1 + US2 + US3 being complete

### User Story Dependencies

- **US1 (P1)**: No story dependencies — can start after Foundation
- **US2 (P2)**: Depends on US1 (`parse_codex()` + fixture files)
- **US3 (P3)**: Depends on US1 (Codex sessions in the pipeline); otherwise independent of US2

### Within Each User Story

- Foundation fixture files (T003–T005) are parallel — different files
- `parse_codex()` implementation (T006–T009) is sequential — same file
- Evals for a story can be written in parallel with implementation (test-first encouraged)
- US2 eval tasks (T013, T014) extend the same test file and can proceed in parallel after T011 is created

### Parallel Opportunities

- T003, T004, T005 — three different fixture files, fully parallel
- T010 (test_codex_missing.py) can be created in parallel with T006–T009 (different file)
- T013, T014 extend the same test file created in T011 — sequential

---

## Parallel Example: User Story 1 Foundation

```bash
# All three fixture JSONL files can be created in parallel (Phase 2):
Task: "Create evals/fixtures/codex/rollouts/session-codex-001.jsonl"
Task: "Create evals/fixtures/codex/rollouts/session-codex-002.jsonl"
Task: "Create evals/fixtures/codex/rollouts/session-codex-003.jsonl"

# EVAL-002 test file (different file from EVAL-001) — parallel with parse_codex() implementation:
Task: "Create evals/test_codex_missing.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T002)
2. Complete Phase 2: Foundational fixtures (T003–T005)
3. Complete Phase 3: US1 implementation + evals (T006–T011)
4. **STOP and VALIDATE**: Run `python -m unittest evals/test_codex_parse.py evals/test_codex_missing.py`
5. Codex sessions appear in report — MVP done

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. Phase 3 → Codex in report (MVP — ships value immediately)
3. Phase 4 → Categorization + detail evals (data quality improvement)
4. Phase 5 → Cross-platform comparisons + cost display (full feature complete)
5. Phase 6 → Regression validation + docs

### Total Task Count

- **Total tasks**: 19
- **US1 tasks**: 6 (T006–T011)
- **US2 tasks**: 3 (T012–T014)
- **US3 tasks**: 3 (T015–T017)
- **Setup/Foundation tasks**: 5 (T001–T005)
- **Polish tasks**: 2 (T018–T019)
- **Parallelizable tasks**: 5 (T003, T004, T005, T010, T019)

### Eval Coverage

| Eval | Story | Task | Coverage |
|------|-------|------|----------|
| EVAL-001 | US1 | T011 | Fixture parsing: session count, tokens, model names |
| EVAL-002 | US1 | T010 | No-DB graceful skip |
| EVAL-003 | US2 | T013 | Category assignment from keyword content |
| EVAL-004 | US2 | T014 | NULL model → rollout JSONL resolution |
| EVAL-005 | US3 | T017 | All-4-platform cross-platform breakdown |
