# Implementation Plan: Codex Platform Support

**Branch**: `004-codex-support` | **Date**: 2026-03-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-codex-support/spec.md`

## Summary

Add OpenAI Codex as a fourth supported tool source in the report generator. This requires a new `parse_codex()` function that reads from the local Codex SQLite session database (`~/.codex/state_5.sqlite`) and, for each thread row, reads an associated JSONL rollout file to resolve the model name and count user turns. Codex sessions are aggregated under the tool key `"codex"` and participate in all existing report sections (platform breakdown, activity timeline, session character, category). Cost estimation is omitted for Codex (only a combined token total is available). The `Session` dataclass gains a `total_tokens` field to carry the combined value.

## Technical Context

**Language/Version**: Python 3.10+ (stdlib only — `sqlite3`, `json`, `os`, `pathlib`)
**Primary Dependencies**: None — `sqlite3` is a stdlib module; no pip installs
**Storage**: `~/.codex/state_5.sqlite` (SQLite) + `~/.codex/sessions/rollout-*.jsonl` (JSONL rollout files referenced by absolute path in the `threads.rollout_path` column)
**Testing**: `python -m unittest discover -s evals -p "test_*.py"` — new `evals/test_codex.py` + synthetic fixtures under `evals/fixtures/codex/`
**Target Platform**: macOS / Linux (same as existing parsers)
**Project Type**: Additional parser module within an existing report generator CLI
**Performance Goals**: No measurable regression — parse 500 Codex sessions within existing 180s time budget
**Constraints**: Python stdlib only; graceful skip if database absent or locked; no cost estimates for Codex

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Evals-First**: EVAL-001 through EVAL-005 defined in spec.md, one per user story plus edge cases.
- [x] **Agent Agnostic**: Parser reads local files directly; no agent-specific APIs. validate.sh unchanged.
- [x] **Zero Dependencies**: `sqlite3` is Python stdlib. No new pip packages.
- [x] **Simplicity**: One new function `parse_codex()`, one new `Session.total_tokens` field, one new CLI arg `--codex-dir`. No new abstractions.
- [x] **Trunk-Based**: This is a spec branch — docs only. Implementation goes on `004-codex-support-impl` after this spec is merged.
- [x] **LLM-Agnostic Insights**: `"codex"` is a data source identifier (same pattern as `"claude_code"`, `"copilot_cli"`). The `"Codex"` display label follows the existing `TOOL_LABELS` pattern. No LLM assumptions hardcoded.

## Project Structure

### Documentation (this feature)

```text
specs/004-codex-support/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── parse-codex.md
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (repository root)

```text
skills/myusage/scripts/
└── generate_report.py          # +parse_codex(), +Session.total_tokens, +--codex-dir arg,
                                 #  +TOOL_LABELS["codex"], +ACCENT_COLORS["codex"]

evals/
├── fixtures/
│   └── codex/
│       ├── state_5.sqlite       # Synthetic SQLite DB (3+ thread rows)
│       └── sessions/
│           ├── rollout-sess-001.jsonl
│           ├── rollout-sess-002.jsonl
│           └── rollout-sess-003.jsonl
└── test_codex.py                # New: EVAL-001 through EVAL-005
```

**Structure Decision**: Flat extension of the existing single-file generator. No new modules or packages. Fixture format mirrors real Codex storage: one SQLite file + sibling `sessions/` folder with JSONL rollout files referenced by absolute path (paths in SQLite fixture will use a helper to rewrite to the test temp dir at test setup time).

## Complexity Tracking

No constitution violations. All gates pass.
