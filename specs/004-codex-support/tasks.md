# Tasks: Codex Platform Support

**Input**: Design documents from `specs/004-codex-support/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅

**Evals**: Per the project constitution, evals are NON-NEGOTIABLE. Every user story phase includes eval tasks. All evals MUST pass before the feature is complete.

**Organization**: All implementation is in `scripts/generate_report.py` (single-file project). Tasks are grouped by user story to enable independent testing of each story. Eval fixtures go in `evals/fixtures/codex/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup

**Purpose**: Ensure eval infrastructure is ready for Codex tests.

- [ ] T001 Create eval test files: `evals/test_codex_us1_discovery.py`, `evals/test_codex_us1_no_db.py`, `evals/test_codex_us2_categorization.py`, `evals/test_codex_us2_model_resolution.py`, `evals/test_codex_us3_cross_platform.py` as empty test files with `import unittest` stubs so the test runner can discover them from the start

- [ ] T002 Create Codex eval fixtures directory structure: `evals/fixtures/codex/` with subdirectories: `state_1.sqlite` (empty file as placeholder), `rollouts/` (directory)

---

## Phase 2: Foundational (Blocking Prerequisites) ✅ COMPLETE

**Purpose**: Create the Codex database discovery and session parsing infrastructure. ALL user story work depends on this phase.

**Status**: ✅ All tasks complete (2026-03-21)

### Database Discovery

- [x] T003 [P] Add module-level constants to `scripts/generate_report.py`:
  - `CODEX_HOME_DIR = Path.home() / ".codex"`
  - `CODEX_DB_PATTERN = "state_*.sqlite"` (for glob matching)
  - Include comment: `# Codex session database location — highest version number takes precedence`

- [x] T004 [P] Implement `discover_codex_database() -> Optional[Path]` function in `scripts/generate_report.py`:
  - Search `~/.codex/` for files matching `state_*.sqlite`
  - Return the highest-numbered version (e.g., prefer `state_5.sqlite` over `state_4.sqlite`)
  - Return `None` if no database files found
  - On error (permission denied, etc.), log a warning to stderr and return `None`

### Codex Session Dataclass

- [x] T005 [P] Add `CodexSession` dataclass to `scripts/generate_report.py` with these fields:
  - ✅ DECISION: Used existing `Session` dataclass with `tool="codex"` instead of creating separate dataclass
  - See `.squad/decisions/inbox/bodie-phase2.md` for architectural rationale

### Model Resolution from Rollout Files

- [x] T006 [P] Implement `extract_model_from_rollout(rollout_path: Path) -> Optional[str]` function in `scripts/generate_report.py`:
  - Open the JSONL file at `rollout_path`
  - Iterate through lines (one JSON object per line)
  - Find the first `turn_context` event
  - Extract and return the `model` field (or equivalent model name field)
  - If not found or file is missing/corrupted, log a warning and return `None`
  - Handle exceptions gracefully (return `None` on parse errors)

### User Message Count from Rollout Files

- [x] T007 [P] Implement `count_user_messages_in_rollout(rollout_path: Path) -> int` function in `scripts/generate_report.py`:
  - Open the JSONL file at `rollout_path`
  - Iterate through lines
  - Count `response_item` events where `role == "user"` and message contains non-system text
  - Return the count (default to 0 if file missing or corrupted)
  - Log warnings on parse errors but do not raise

### Database Parsing

- [x] T008 Implement `parse_codex_database(db_path: Path) -> List[Session]` function in `scripts/generate_report.py`:
  - Connect to SQLite database at `db_path`
  - Query the `threads` table
  - For each row, extract session metadata (id, created_at, updated_at, working_directory, tokens_used, cli_version, source, approval_mode, rollout_path)
  - If `model` field is NULL, resolve via `extract_model_from_rollout()` using the `rollout_path` from the row
  - Call `count_user_messages_in_rollout()` to populate `user_message_count`
  - Extract `first_user_message` from the rollout file (search for the first `response_item` with `role == "user"`)
  - Return a list of `Session` objects with `tool="codex"`
  - On database error (corrupted, locked, schema mismatch), log a warning and return an empty list

### Integration into Report Builder

- [x] T009 [P] Modify `main()` in `scripts/generate_report.py` to call `discover_codex_database()` after existing platform parsing:
  - Call `db_path = discover_codex_database()` after Copilot CLI parsing
  - If `db_path` is not None, call `codex_sessions = parse_codex_database(db_path)`
  - Merge `codex_sessions` into `all_sessions` list
  - Apply cutoff filter if --days specified
  - Log info-level message if Codex database found and parsed successfully
  - Log info-level message if Codex database not found

**Checkpoint**: ✅ Database discovery, model resolution, message counting, and session parsing all implemented and wired. Report still generates without errors when Codex database is present or absent.

---

## Phase 3: User Story 1 — Codex Sessions in Usage Report (Priority: P1) 🎯 MVP

**Goal**: Generate a report that includes discovered Codex sessions in the main platform breakdown and timeline.

**Independent Test**: Run `python -m unittest evals/test_codex_us1_discovery.py evals/test_codex_us1_no_db.py` — all EVAL-001 and EVAL-002 pass.

### Implementation for User Story 1

- [ ] T010 [US1] Create `evals/fixtures/codex/state_1.sqlite` with a populated `threads` table containing 3+ synthetic Codex sessions:
  - Session 1: `id="uuid-001"`, `created_at="2026-03-01T10:00:00Z"`, `updated_at="2026-03-01T10:30:00Z"`, `tokens_used=1500`, `model="claude-opus-4.6"`, `cli_version="1.2.3"`, `source="cli"`, `approval_mode="agentic"`
  - Session 2: `id="uuid-002"`, `created_at="2026-03-02T14:00:00Z"`, `updated_at="2026-03-02T15:00:00Z"`, `tokens_used=2800`, `model=NULL` (to test resolution), `cli_version="1.2.3"`, `source="vscode"`, `approval_mode="on-request"`
  - Session 3: `id="uuid-003"`, `created_at="2026-03-03T08:00:00Z"`, `updated_at="2026-03-03T09:15:00Z"`, `tokens_used=900`, `model="claude-haiku-4.5"`, `cli_version="1.2.3"`, `source="cli"`, `approval_mode="network-disabled"`
  - Each session record must include `rollout_path` pointing to a JSONL file in `evals/fixtures/codex/rollouts/`

- [ ] T011 [P] [US1] Create rollout JSONL files for each fixture session:
  - `evals/fixtures/codex/rollouts/session-001.jsonl`: First user message "Debug the API timeout", 8 user messages total, includes `turn_context` with `model="claude-opus-4.6"`
  - `evals/fixtures/codex/rollouts/session-002.jsonl`: First user message "Generate test cases", 10 user messages total, includes `turn_context` with `model="claude-opus-4.6"` (to resolve NULL from db)
  - `evals/fixtures/codex/rollouts/session-003.jsonl`: First user message "Plan the refactor", 4 user messages total, includes `turn_context` with `model="claude-haiku-4.5"`
  - Each file must contain valid JSONL with `session_meta`, `turn_context`, and `response_item` events in order

- [ ] T012 [P] [US1] Implement EVAL-001 in `evals/test_codex_us1_discovery.py`:
  - Load the Codex fixtures from `evals/fixtures/codex/`
  - Call `parse_codex_database(evals/fixtures/codex/state_1.sqlite)`
  - Assert returned list has 3 sessions
  - Assert session counts: Session 1 = 1500 tokens, Session 2 = 2800 tokens, Session 3 = 900 tokens
  - Assert model resolution: Session 2's model is resolved from rollout (not NULL)
  - Assert user message counts: Session 1 = 8, Session 2 = 10, Session 3 = 4
  - Call `build_report(all_sessions_including_codex)` and assert output contains "codex" or "Codex" (platform entry exists)
  - Assert platform breakdown includes Codex with correct session count (3) and token total (5200)

- [ ] T013 [P] [US1] Implement EVAL-002 in `evals/test_codex_us1_no_db.py`:
  - Call `build_report([])` with an empty session list but with `discover_codex_database()` returning None
  - Assert report completes without error
  - Assert report is valid HTML and contains valid JSON report data
  - Assert no Codex platform entry appears in the output (graceful omission)

**Checkpoint**: EVAL-001 and EVAL-002 pass. Codex sessions are discovered, parsed, merged into the report, and included in platform breakdown. No errors when Codex database is absent.

---

## Phase 4: User Story 2 — Codex Session Detail & Categorization (Priority: P2)

**Goal**: Classify Codex sessions into categories (Debugging, Code Generation, etc.) and character types (autonomous, deeply engaged, general) using the same logic as other platforms.

**Independent Test**: Run `python -m unittest evals/test_codex_us2_categorization.py evals/test_codex_us2_model_resolution.py` — EVAL-003 and EVAL-004 pass.

### Implementation for User Story 2

- [ ] T014 [US2] Integrate Codex sessions into existing `categorize_session()` logic in `scripts/generate_report.py`:
  - Ensure Codex sessions (with `tool="codex"`) are passed through the same categorization function as other platforms
  - Use `first_user_message` from CodexSession as the categorization input (same as `first_message` for other tools)
  - Verify no Codex-specific branching is needed — reuse existing keyword matching

- [ ] T015 [US2] Integrate Codex sessions into existing `classify_session_character()` logic in `scripts/generate_report.py`:
  - Ensure Codex sessions are classified as autonomous, deeply engaged, or general using the same duration/message count thresholds as other platforms
  - Verify `user_message_count` is used correctly in classification logic

### Evals for User Story 2

- [ ] T016 [P] [US2] Implement EVAL-003 in `evals/test_codex_us2_categorization.py`:
  - Using fixture sessions, verify categorization:
    - Session 1 (first_message="Debug the API timeout") → categorized as "Debugging"
    - Session 2 (first_message="Generate test cases") → categorized as "Code Generation" or "Testing"
    - Session 3 (first_message="Plan the refactor") → categorized as "Planning"
  - Assert categories match expected values using the same logic applied to Claude Code and Copilot sessions
  - Verify character classification (Session 1 & 2 = "deeply engaged", Session 3 = "general") using message count and duration

- [ ] T017 [P] [US2] Implement EVAL-004 in `evals/test_codex_us2_model_resolution.py`:
  - Using fixture Session 2 (model=NULL in database):
    - Call `parse_codex_database()` and extract Session 2
    - Assert `session.model == "claude-opus-4.6"` (resolved from rollout file)
  - Using fixtures where rollout file is missing:
    - Create a fixture session record pointing to a non-existent rollout file
    - Call `parse_codex_database()` and extract that session
    - Assert the session is still returned (with model=NULL or a default)
    - Assert a warning is logged but parsing continues

**Checkpoint**: Codex sessions are categorized and classified using existing logic. EVAL-003 and EVAL-004 pass. Model resolution handles both database and rollout file sources.

---

## Phase 5: User Story 3 — Codex Data in Cross-Platform Comparisons (Priority: P3)

**Goal**: Include Codex sessions in aggregate charts and timelines alongside Claude Code and Copilot.

**Independent Test**: Run `python -m unittest evals/test_codex_us3_cross_platform.py` — EVAL-005 passes.

### Implementation for User Story 3

- [ ] T018 [US3] Verify Codex sessions appear in `activity_timeline` (time-series chart):
  - Ensure Codex sessions (with their `created_at` timestamps) are included in the timeline aggregation
  - Assert timeline includes all three platforms: claude_code, copilot, codex

- [ ] T019 [US3] Verify Codex sessions appear in `category_distribution` chart:
  - Ensure Codex sessions (after categorization) are aggregated into the category breakdown
  - Assert chart includes categories from Codex alongside Claude Code and Copilot

- [ ] T020 [US3] Verify Codex sessions appear in `character_distribution` chart:
  - Ensure Codex sessions (after classification) are aggregated into the character breakdown
  - Assert chart includes character types from Codex alongside other platforms

### Evals for User Story 3

- [ ] T021 [P] [US3] Implement EVAL-005 in `evals/test_codex_us3_cross_platform.py`:
  - Create a combined fixture set with sessions from all four platforms:
    - Claude Code: 2 sessions
    - Copilot CLI: 1 session
    - Copilot VS Code: 1 session
    - Codex: 3 sessions (from Phase 3 fixtures)
  - Call `build_report(all_platforms_combined)`
  - Extract the report JSON and verify:
    - Platform breakdown includes all 4 platforms with correct session counts (codex=3)
    - Activity timeline includes data points from all platforms
    - Category distribution includes Codex categories
    - Character distribution includes Codex character types
  - Assert no platform is missing and no data is dropped

**Checkpoint**: EVAL-005 passes. Codex sessions are included in all cross-platform aggregates (platform breakdown, timeline, category/character distributions).

---

## Phase 6: Evals Infrastructure & Cost Representation

**Purpose**: Add Codex evals to the evals.json registry and ensure cost display is correct (—).

- [ ] T022 Add Codex evals to `evals/evals.json`:
  - EVAL-001 (US1 discovery): `test_codex_us1_discovery`
  - EVAL-002 (US1 no DB): `test_codex_us1_no_db`
  - EVAL-003 (US2 categorization): `test_codex_us2_categorization`
  - EVAL-004 (US2 model resolution): `test_codex_us2_model_resolution`
  - EVAL-005 (US3 cross-platform): `test_codex_us3_cross_platform`
  - Each entry includes: id, title, description, acceptance_criteria

- [ ] T023 [P] Verify cost representation in HTML report:
  - Ensure Codex sessions display `—` (dash) in cost columns (no cost breakdown)
  - Ensure a footnote is added to the report explaining cost limitation: "Cost estimates not available for Codex. The session database provides only combined token totals without input/output breakdown."

---

## Phase 7: Final Validation & Documentation

**Purpose**: Ensure all evals pass, documentation is complete, and the feature is ready to ship.

- [ ] T024 [P] Run all evals locally:
  ```bash
  python -m unittest discover -s evals -p "test_codex_*.py" -v
  ```
  - Assert all 5 Codex evals pass (EVAL-001 through EVAL-005)
  - Assert no regressions in existing evals (run full suite)

- [ ] T025 [P] Verify graceful error handling:
  - Test with corrupted Codex database (invalid SQLite file)
  - Test with locked Codex database (simulated via mock or read-only file)
  - Test with missing rollout files
  - Verify each scenario logs a warning and report generation continues
  - Assert no exceptions are raised

- [ ] T026 [P] Update `CHANGELOG.md`:
  - Add entry: "feat: Add Codex platform support to usage insights report (004)"
  - Include: sessions auto-discovered from ~/.codex/state_N.sqlite, model resolution from rollout files, categorization and character classification, integrated into all report sections, graceful handling when Codex unavailable

- [ ] T027 [P] Update `README.md` if necessary:
  - Add Codex to the supported platforms list (if README lists them)
  - Include note about cost limitation (—) in cost section

**Checkpoint**: All 5 Codex evals pass. All regressions fixed. Error handling verified. Documentation updated. Feature ready for merge.

---

## Acceptance Criteria for Feature Completion

✅ **EVAL-001**: Codex sessions discovered and parsed from fixtures; report includes platform entry with correct counts and tokens  
✅ **EVAL-002**: Report generates successfully with no Codex database present; Codex section gracefully omitted  
✅ **EVAL-003**: Codex sessions categorized consistently with other platforms; character classification applied  
✅ **EVAL-004**: Model resolution handles both database and rollout file sources; missing files logged as warnings  
✅ **EVAL-005**: Cross-platform aggregates include Codex sessions in all charts and timelines  
✅ **No regressions**: Existing evals for Claude Code and Copilot still pass  
✅ **Documentation**: CHANGELOG and README updated  
✅ **Error handling**: All graceful degradation scenarios verified  
✅ **Zero new dependencies**: Only stdlib (sqlite3, json, pathlib)  

---

## Testing Command

Once all phases are complete, run:

```bash
# Run Codex evals only
python -m unittest discover -s evals -p "test_codex_*.py" -v

# Run full evals suite (including regressions)
python -m unittest discover -s evals -p "test_*.py" -v

# Generate sample report
python scripts/generate_report.py
```

Expected outcome: All evals pass, report generates without errors, Codex section appears in output.
