# Research: Codex Platform Support

**Feature**: 004-codex-support
**Date**: 2026-03-26

---

## Decision 1: Storage backend for Codex session data

**Decision**: SQLite via Python stdlib `sqlite3` module
**Rationale**: The Codex CLI stores all sessions in `~/.codex/state_5.sqlite`. Python's built-in
`sqlite3` module provides a complete, zero-dependency SQL interface. No additional packages needed.
The database version is a constant (`state_5.sqlite`) in the current Codex CLI source; schema
version discovery (finding the highest-N file) is a robustness measure for forward compatibility.
**Alternatives considered**:
- Parsing raw SQLite binary format manually — rejected; reinvents a solved problem, fragile
- Third-party `sqlalchemy` — rejected; violates Zero Dependencies principle

---

## Decision 2: Model name resolution fallback chain

**Decision**: `threads.model` column → `turn_context` event in rollout JSONL → `None`
**Rationale**: The `threads.model` column is nullable (added in migration 0020). When NULL the
model was not stored at write time and must be recovered from the rollout file. The first
`turn_context` event's `payload.model` field is the canonical source of truth for the model used
in that session. If the rollout file is missing or the `turn_context` event is absent, model
remains `None` — consistent with how other parsers handle unknown model names.
**Alternatives considered**:
- Default to a hardcoded model string — rejected; violates LLM-Agnostic Insights principle
- Read all `event_msg` token events — rejected; model name is not in token events

---

## Decision 3: User turn counting from rollout JSONL

**Decision**: Count `response_item` lines where `payload.role == "user"` and content contains
non-system text (text not enclosed in `<` `>` XML-style tags matching system prefixes)
**Rationale**: `response_item` events mirror the `openai.responses` API format. User turns are
reliably identified by `role: "user"`. System-injected messages (environment context,
instructions) are wrapped in angle-bracket tags and should be excluded from the count — matching
the filtering applied to Claude Code messages in `_is_system_message()`.
**Alternatives considered**:
- `event_msg` user_message events — these are lifecycle signals, not the actual message content
- Plain line counting — too fragile; includes assistant turns

---

## Decision 4: Token data representation in Session dataclass

**Decision**: Add `total_tokens: Optional[int]` field to `Session`. For Codex sessions, set
`input_tokens = None`, `output_tokens = None`, `total_tokens = threads.tokens_used`. For all
other tools, `total_tokens = None`.
**Rationale**: The Codex database only stores a combined `tokens_used` total with no
input/output split. Storing it in `input_tokens` would misrepresent the semantics. A dedicated
`total_tokens` field cleanly handles this case and future tools with similar limitations.
The existing `compute_session_costs()` function already skips tools other than `copilot_vscode`
and `copilot_cli`, so Codex cost calculation is naturally excluded.
**Alternatives considered**:
- Store `tokens_used` in `input_tokens` as a proxy — rejected; misleading semantics, would cause
  incorrect cost estimates if cost logic is ever extended
- Do not store token count at all — rejected; FR-007 requires Codex tokens in aggregate sections

---

## Decision 5: Fixture format for evals

**Decision**: A pre-created `state_5.sqlite` binary file in `evals/fixtures/codex/` plus sibling
JSONL rollout files in `evals/fixtures/codex/sessions/`. Test setup rewrites the `rollout_path`
values in a copied (in-memory or temp-dir) version of the SQLite database to point to the
correct absolute paths before running the parser.
**Rationale**: Mirrors the real Codex storage layout exactly (SQLite + sibling sessions folder).
The path-rewriting step is minimal (single UPDATE statement per test run) and ensures fixtures
work from any checkout directory.
**Alternatives considered**:
- Hardcode absolute paths in the fixture SQLite — rejected; breaks on any checkout path change
- Create the SQLite entirely in test setUp — more code, less transparent; the fixture file itself
  serves as documentation of the expected schema

---

## Decision 6: CLI argument for Codex directory

**Decision**: Add `--codex-dir` argument defaulting to `~/.codex`
**Rationale**: Consistent with `--claude-dir`, `--vscode-dir`, `--copilot-cli-dir` pattern.
Allows easy override in evals and by users with non-standard install locations.
The parser detects `state_5.sqlite` (or highest-versioned `state_N.sqlite`) within this directory.
**Alternatives considered**:
- Auto-detect only `~/.codex` with no override — rejected; evals could not run without touching
  the real user database

---

## Decision 7: Schema version discovery

**Decision**: Glob `~/.codex/state_*.sqlite`, extract the integer N from each filename, use the
file with the highest N. Fall back gracefully (skip Codex) if no matching file is found.
**Rationale**: The Codex CLI ships `state_5.sqlite` today but may increment the version on
schema changes. Future-proofing with a glob is three lines of code and zero complexity cost.
**Alternatives considered**:
- Hard-code `state_5.sqlite` — simpler today but will silently produce no data when Codex
  increments to state_6.sqlite; rejected on robustness grounds
