# Implementation Plan: Codex Platform Support

**Branch**: `004-codex-support` | **Date**: 2026-03-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-codex-support/spec.md`

## Summary

Extend `skills/myusage/scripts/generate_report.py` to ingest Codex session data from the
local SQLite database (`~/.codex/state_N.sqlite`), read per-session rollout JSONL files for
model resolution and message counting, and include Codex sessions in all existing report
sections (platform breakdown, activity timeline, session character distribution, category
distribution). Codex cost display shows `—` with a footnote because the database provides
only a combined token total without an input/output split.

All work is inside `generate_report.py`, a new `parse_codex()` parser function, three eval
fixture sessions (SQLite + JSONL), and eval tests. No new dependencies — `sqlite3` is Python
stdlib.

## Technical Context

**Language/Version**: Python 3.10+ (stdlib only — per constitution Principle III)  
**Primary Dependencies**: `sqlite3` stdlib module (already built-in — zero net-new dependencies)  
**Storage**: `~/.codex/state_N.sqlite` (read-only SQLite) + rollout JSONL files (read-only)  
**Testing**: `python -m unittest discover -s evals -p "test_*.py"`  
**Target Platform**: macOS/Linux developer machine (same as existing feature 001)  
**Project Type**: CLI tool — single Python script producing a self-contained HTML file  
**Performance Goals**: Report generation in under 10 seconds on typical session history. SQLite query is a single `SELECT *` on the `threads` table; no performance concern.  
**Constraints**: No pip dependencies; no network calls; graceful skip when `~/.codex/` is absent.  
**Scale/Scope**: Single developer's local session history; no multi-user concerns.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Evals-First**: EVAL-001 through EVAL-005 defined in spec, covering all three user stories.
- [x] **Agent Agnostic**: Implementation is in a Python script with no agent-specific syntax. No CLAUDE.md or Copilot-specific execution paths in generator code.
- [x] **Zero Dependencies**: `sqlite3` is Python stdlib — zero net-new runtime dependencies. Chart.js remains the only approved exception.
- [x] **Simplicity**: One new parser function + two new dataclass fields + fixture files + eval tests. No new abstractions. Minimum viable design.
- [x] **Trunk-Based**: This is a spec branch (docs only). Implementation will happen on `004-codex-support-impl` after this spec merges to `main`.
- [x] **LLM-Agnostic Insights**: Codex sessions are stored under tool identifier `"codex"` derived from the data, not hardcoded. Report labels use existing neutral terminology. Eval fixtures included per FR-010/FR-011.

## Project Structure

### Documentation (this feature)

```text
specs/004-codex-support/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── codex-parser.md
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (repository root)

```text
skills/myusage/scripts/
└── generate_report.py       # All implementation changes here

evals/
├── fixtures/
│   └── codex/               # New: Codex fixture data
│       ├── state_5.sqlite   # Pre-built SQLite database (3 synthetic sessions)
│       └── rollouts/        # Per-session JSONL rollout files
│           ├── session-codex-001.jsonl
│           ├── session-codex-002.jsonl
│           └── session-codex-003.jsonl
└── test_codex_*.py          # New eval tests for Codex parsing
```

**Structure Decision**: Single-file project. All implementation in `generate_report.py`.
Eval fixtures follow the same `evals/fixtures/<tool>/` convention as `copilot_cli` and
`copilot_vscode`. The SQLite fixture is a committed binary (minimal, ~20KB).

## Design Decisions

### 1. New `parse_codex(codex_dir: str) -> List[Session]` function

Follows the same signature and structure as `parse_copilot_cli()` and `parse_claude_code()`.
- `codex_dir` defaults to `~/.codex/` in `main()` via `--codex-dir` CLI arg
- When `codex_dir` does not exist, returns `[]` (graceful skip — satisfies FR-009)
- Globs for `state_*.sqlite` files, sorts by version number N, picks the highest
- Opens the database with `sqlite3` (read-only mode via `uri=True`)
- Queries the `threads` table; builds one `Session` per row
- For each session, reads the rollout JSONL file (path from `threads.rollout_path`) to resolve model name and count user messages

### 2. Token storage strategy

The Codex `threads` table provides only `tokens_used` (combined total; no input/output split).
Per FR-012, cost estimation is impossible and must display `—`.

**Decision**: Store `tokens_used` in `session.input_tokens`; set `session.output_tokens = None`.
This re-uses the existing field without adding a new `Session` field. The `compute_session_costs()`
function already returns early if `output_tokens is None` for Copilot-style cost calculation.
For Codex, the function MUST explicitly skip cost computation (set `estimated_cost_usd = None`).
The HTML renderer checks `session.tool == "codex"` to display `—` in cost columns with a footnote.

**No new `Session` dataclass fields required for token data.** One new field is needed for source
metadata (see Decision 3).

### 3. Source metadata (`cli` vs `vscode`) storage

FR-008 requires that `source` (cli/vscode) is stored per-session as metadata but does NOT split
Codex into separate chart series.

**Decision**: Add one new optional field to `Session`:
```python
codex_source: Optional[str] = None   # "cli" or "vscode" — Codex sessions only
```
This field is `None` for all non-Codex sessions. The report renders it in per-session detail
views where applicable, but the `tool` value is always `"codex"` for chart aggregation.

### 4. Model resolution from rollout JSONL

When `threads.model` is NULL (or empty string), the parser reads the rollout JSONL file and
scans for the first `turn_context` event. The model name is extracted from
`event["data"]["model"]` (or `event["model"]` — both layouts handled).

If the rollout file is missing or unreadable, `session.model` remains `None`.

### 5. Message counting from rollout JSONL

FR-004: count `response_item` events where `role == "user"` and content is non-system text.

**Non-system text definition**: content is non-empty AND does not match the existing
`_is_system_message()` helper already defined in `generate_report.py`.

### 6. Session character and category classification

Use existing `classify_session_character()` and `categorize_session()` functions unchanged.
The `categorize_session()` function uses the first user `Message.content` in `session.messages`.
The `parse_codex()` parser populates `session.messages` with `Message` objects constructed from
`response_item` events in the rollout JSONL (user role only — same pattern as other parsers).

### 7. Eval fixtures: SQLite binary vs. in-test construction

**Decision**: Construct fixture SQLite databases programmatically inside test `setUp()` using
`sqlite3` and `tempfile`. No binary SQLite file committed to git. The rollout JSONL fixture
files ARE committed as plain text files (same as existing `events.jsonl` fixtures).

**Rationale**: Binary SQLite files in git are opaque to reviewers and hard to modify.
Constructing them in `setUp()` keeps fixtures readable, version-controlled as text, and
consistent with how the existing `evals/test_pru_cli.py` constructs in-test `Session` objects
for edge-case tests.

## Complexity Tracking

No constitution violations. All gates pass.
