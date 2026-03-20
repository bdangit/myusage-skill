# Tasks: Copilot PRU and Claude Token Cost Comparison

**Input**: Design documents from `specs/002-copilot-pru-cost/`
**Prerequisites**: plan.md ✅, spec.md ✅

**Evals**: Per the project constitution, evals are NON-NEGOTIABLE. Every user story phase
includes eval tasks. All evals MUST pass before the feature is complete.

**Organization**: All implementation is in `scripts/generate_report.py` (single-file project).
Tasks are grouped by user story to enable independent testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup

**Purpose**: Ensure eval infrastructure is ready for cost and PRU tests.

- [ ] T001 Create `evals/test_pru_vscode.py`, `evals/test_pru_cli.py`, `evals/test_pru_missing.py`, `evals/test_claude_cost.py`, `evals/test_report_cost_display.py`, `evals/test_report_partial_data.py` as empty test files with `import unittest` stubs so the test runner can discover them from the start

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extend the `Session` dataclass and add the price tables and cost computation
function. ALL user story work depends on this phase.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T002 Add three optional fields to the `Session` dataclass in `scripts/generate_report.py`: `effective_prus: Optional[float] = None`, `estimated_cost_usd: Optional[float] = None`, and `model_request_counts: Optional[Dict[str, int]] = None`

- [ ] T003 [P] Add `PRU_MULTIPLIERS: Dict[str, float]` module-level dict to `scripts/generate_report.py` with entries for `gpt-4o` (1.0), `claude-haiku-4.5` (1.0), `claude-sonnet-4-6` (1.0), `claude-opus-4-6` (3.0); also add `PRU_DEFAULT_MULTIPLIER = 1.0` and `PRU_UNIT_PRICE_USD = 0.04`; include a `# last verified: 2026-03-17` comment above the dict

- [ ] T004 [P] Add `TOKEN_PRICES: Dict[str, Dict[str, float]]` module-level dict to `scripts/generate_report.py` with per-million-token USD prices for `claude-haiku-4.5` (input: 0.80, output: 4.00), `claude-sonnet-4-6` (input: 3.00, output: 15.00), `claude-opus-4-6` (input: 15.00, output: 75.00); include a `# last verified: 2026-03-17` comment above the dict

- [ ] T005 Add `compute_session_costs(sessions: List[Session]) -> None` function to `scripts/generate_report.py` after the price table dicts; the function mutates sessions in-place and must contain two stubs — one for Copilot PRU logic (US1) and one for Claude token cost logic (US2) — each as `pass` initially; the function is called once at the end of `build_report()` before the function returns

- [ ] T006 Wire the `compute_session_costs(all_sessions)` call into `build_report()` in `scripts/generate_report.py`, placing it after all sessions have been collected and classified but before the function returns the `InsightsReport`

**Checkpoint**: `Session` dataclass has new fields; price tables are defined; `compute_session_costs` is wired but contains stubs. Report still generates without errors.

---

## Phase 3: User Story 1 — Extract and Normalize Copilot Sessions (Priority: P1) 🎯 MVP

**Goal**: Compute `effective_prus` and `estimated_cost_usd` for Copilot VS Code and CLI
sessions from local files only, using per-model PRU multipliers.

**Independent Test**: Run `python -m unittest evals/test_pru_vscode.py evals/test_pru_cli.py evals/test_pru_missing.py` — all EVAL-001, EVAL-002, and EVAL-003 pass.

### Implementation for User Story 1

- [ ] T007 [US1] Extend `parse_copilot_vscode` in `scripts/generate_report.py` to populate `session.model_request_counts` as a `Dict[str, int]` counting each `req.get("modelId")` occurrence across all requests; fall back to `{session.model: len(user_msgs)}` when all requests share the same model or when `modelId` is absent from requests

- [ ] T008 [US1] Implement the Copilot PRU branch in `compute_session_costs` in `scripts/generate_report.py`: for each session where `session.tool` is `copilot_vscode` or `copilot_cli`, iterate `model_request_counts` (falling back to `{session.model: session.message_count}` when `model_request_counts` is None), look up the multiplier from `PRU_MULTIPLIERS` (default `PRU_DEFAULT_MULTIPLIER` for unknowns and emit a `stderr` warning), compute `effective_prus = sum(count × multiplier)`, compute `estimated_cost_usd = effective_prus × PRU_UNIT_PRICE_USD`, set both fields on the session

### Evals for User Story 1

- [ ] T009 [P] [US1] Implement EVAL-001 in `evals/test_pru_vscode.py`: parse `evals/fixtures/copilot_vscode/workspace-abc123/chatSessions/session-vscode-001.json` through `parse_copilot_vscode`, run `compute_session_costs`, assert `session.message_count == 5`, `session.model == "claude-haiku-4.5"`, `session.effective_prus == 5.0` (5 requests × 1.0 multiplier), and `session.estimated_cost_usd == pytest.approx(0.20, rel=0.05)`

- [ ] T010 [P] [US1] Implement EVAL-002 in `evals/test_pru_cli.py`: parse both `evals/fixtures/copilot_cli/session-cli-001/events.jsonl` and `evals/fixtures/copilot_cli/session-cli-002/events.jsonl` through `parse_copilot_cli`, run `compute_session_costs` on the result, assert each session has correct `message_count`, `effective_prus`, and `estimated_cost_usd`; verify `input_tokens` and `output_tokens` are populated from `assistant.usage` events

- [ ] T011 [US1] Implement EVAL-003 in `evals/test_pru_missing.py`: call `parse_copilot_vscode` and `parse_copilot_cli` with a path to a non-existent directory, assert both return empty lists, then call `build_report([])` and assert it returns an `InsightsReport` without raising

**Checkpoint**: Copilot PRU cost derivation works from local files. EVAL-001, EVAL-002, EVAL-003 all pass.

---

## Phase 4: User Story 2 — Extract and Normalize Claude Code Sessions (Priority: P2)

**Goal**: Compute `estimated_cost_usd` for Claude Code sessions by applying the token price
schedule to `input_tokens` and `output_tokens` already parsed by feature 001.

**Independent Test**: Run `python -m unittest evals/test_claude_cost.py` — EVAL-004 passes.

### Implementation for User Story 2

- [ ] T012 [US2] Implement the Claude Code cost branch in `compute_session_costs` in `scripts/generate_report.py`: for each session where `session.tool == "claude_code"`, if `session.input_tokens` and `session.output_tokens` are not None, look up `TOKEN_PRICES.get(session.model)`; if found, compute `estimated_cost_usd = (input_tokens / 1_000_000 × price["input"]) + (output_tokens / 1_000_000 × price["output"])`; if model not in `TOKEN_PRICES`, leave `estimated_cost_usd = None` and emit a `stderr` warning with the model name

### Evals for User Story 2

- [ ] T013 [US2] Implement EVAL-004 in `evals/test_claude_cost.py`: parse all fixtures in `evals/fixtures/claude_code/project-alpha/` through `parse_claude_code`, run `compute_session_costs`, assert each session with a recognized model has a non-None `estimated_cost_usd`; compute the expected cost manually from the fixture token counts and the `TOKEN_PRICES` table and assert within ±10%; assert sessions with an unrecognized model name (if any) have `estimated_cost_usd == None`

**Checkpoint**: Claude Code token cost estimation works. EVAL-004 passes.

---

## Phase 5: User Story 3 — Cost Figures in Report (Priority: P3)

**Goal**: Extend the existing per-tool stat display in `render_html()` to show estimated
cost and effective PRU counts per tool, with "estimated" labels and "N/A" for absent fields.

**Independent Test**: Run `python -m unittest evals/test_report_cost_display.py evals/test_report_partial_data.py` — EVAL-005 and EVAL-006 pass.

### Implementation for User Story 3

- [ ] T014 [US3] Extend `extract_data()` in `scripts/generate_report.py` to include cost rollup in the returned data dict: for each tool snapshot, sum `estimated_cost_usd` across sessions (skipping `None` values); sum `effective_prus` across sessions (Copilot only); produce a `monthly_cost` breakdown (YYYY-MM → total `estimated_cost_usd`) over the trailing 6-month window; store as `cost_summary` keyed by tool name in the data dict

- [ ] T015 [US3] Extend the per-tool stat section in `render_html()` in `scripts/generate_report.py` to render the cost fields from `extract_data()`: display "Estimated Cost" total with an "(estimated)" label next to it; display "Effective PRUs" for Copilot tools only; display "N/A" (not zero) when `estimated_cost_usd` is None or when a field does not apply to the tool; ensure all text labels use the session's `tool` value (e.g., `copilot_vscode`, `claude_code`) — no hardcoded vendor strings

### Evals for User Story 3

- [ ] T016 [P] [US3] Implement EVAL-005 in `evals/test_report_cost_display.py`: load fixture sessions from all three sources, run `compute_session_costs`, call `render_html()` with a temp output path, read the generated HTML, assert: (a) "Estimated Cost" text appears in the HTML, (b) "(estimated)" label appears, (c) a numeric cost value appears for each tool with data, (d) "Effective PRUs" text appears for a Copilot tool section, (e) no hardcoded strings "Copilot", "Claude", or "GitHub" appear in the HTML template text (vendor names may appear only as data values from fixture sessions)

- [ ] T017 [P] [US3] Implement EVAL-006 in `evals/test_report_partial_data.py`: run `render_html()` with sessions from only one tool source (e.g., Claude Code only), assert the report generates without error and the missing tools display "N/A" rather than zero or an error; also test with empty session list and assert report generates cleanly

**Checkpoint**: All three user stories functional. All 6 evals pass.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T018 Run the full eval suite `python -m unittest discover -s evals -p "test_*.py"` and confirm zero failures; fix any regressions in existing evals introduced by the `Session` dataclass changes

- [x] T019 Audit the HTML added in T015 for hardcoded vendor names: grep the new template strings in `render_html()` for "Claude", "Copilot", "GitHub", "GPT", "Anthropic" — none should appear as static text; all tool labels must come from `session.tool` or snapshot keys

- [x] T020 Run `.specify/scripts/bash/update-agent-context.sh claude` from repo root to update agent context file with the new `PRU_MULTIPLIERS`, `TOKEN_PRICES`, and `compute_session_costs` additions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1)**: Depends on Phase 2 — can start as soon as `compute_session_costs` stub is wired
- **Phase 4 (US2)**: Depends on Phase 2 — independent of Phase 3
- **Phase 5 (US3)**: Depends on Phase 3 AND Phase 4 (needs both cost fields populated)
- **Phase 6 (Polish)**: Depends on all prior phases

### User Story Dependencies

- **US1 (P1)**: Requires Phase 2 complete. Independent of US2.
- **US2 (P2)**: Requires Phase 2 complete. Independent of US1.
- **US3 (P3)**: Requires US1 AND US2 complete (both cost fields must be set before display).

### Parallel Opportunities Within Phases

- T003 and T004 (price tables): fully parallel — different dicts, same file section
- T009 and T010 (EVAL-001 and EVAL-002): fully parallel — different test files
- T016 and T017 (EVAL-005 and EVAL-006): fully parallel — different test files

---

## Parallel Example: User Story 1

```bash
# After T006 is done, launch these in parallel:
Task T007: "Extend parse_copilot_vscode for model_request_counts"
Task T008: "Implement Copilot PRU branch in compute_session_costs"
# T008 depends on T007 completing first

# After T007+T008, launch evals in parallel:
Task T009: "EVAL-001 in evals/test_pru_vscode.py"
Task T010: "EVAL-002 in evals/test_pru_cli.py"
# T011 can follow in sequence (tests missing-data path)
```

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: Foundational (T002–T006)
3. Complete Phase 3: US1 (T007–T011)
4. **STOP and VALIDATE**: Run EVAL-001, EVAL-002, EVAL-003 — all must pass
5. PRU cost derivation for Copilot is complete and verified

### Incremental Delivery

1. Phase 1 + Phase 2 → Foundation ready (dataclass + price tables + wired stub)
2. Phase 3 → Copilot PRU cost working and eval-verified
3. Phase 4 → Claude Code token cost working and eval-verified
4. Phase 5 → Cost figures visible in report, all evals passing
5. Phase 6 → Clean, audited, agent context updated

---

## Notes

- All implementation is in `scripts/generate_report.py` — no new files except eval test files
- `Session.message_count` is the canonical interaction count (spec's `interaction_count` maps to this)
- `model_request_counts` enables per-model PRU accuracy for VS Code; CLI uses `message_count` fallback
- Cost figures in the report must always carry an "estimated" label (FR-008)
- "N/A" not zero for absent fields (FR-010, SC-007)
- No hardcoded vendor names in HTML template text (FR-011, constitution Principle VI)
