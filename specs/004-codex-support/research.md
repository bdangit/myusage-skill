# Research: Codex Platform Support

## Codex Session Data Storage

**Decision**: Read from SQLite database at `~/.codex/state_N.sqlite` (N = highest version number).

**Rationale**: 
- Codex stores session metadata in a local SQLite database for fast queries and persistence.
- Using the highest-versioned file allows schema evolution without breaking existing support.
- SQLite is built into Python stdlib (`sqlite3`), so no new dependencies required.

**Alternatives Considered**:
- Read from Codex API: Not applicable — Codex CLI does not expose a public API for session history.
- Read from logs directory: Would require parsing multiple files and would be slower than database queries.

**Source Files**:
- `~/.codex/state_N.sqlite` — the primary database file
- `~/.codex/rollouts/` — directory containing JSONL rollout files referenced by session records

## Session Metadata Extraction

**Decision**: Extract from the `threads` table in the Codex database. Fields: id, created_at, updated_at, working_directory, tokens_used, cli_version, source, approval_mode, rollout_path.

**Rationale**:
- The `threads` table is the canonical source for session summaries in Codex.
- These fields directly map to user story requirements (US1: session count, tokens, date range, models).
- `rollout_path` points to the JSONL file containing detailed event logs needed for message count and model resolution.

**Alternatives Considered**:
- Query only the threads table without rollout files: Would miss model name (when NULL) and user message count, incomplete for US2 categorization.

## Model Name Resolution

**Decision**: For each session, check the `model` field in the thread record. If NULL, open the referenced rollout JSONL file and search for a `turn_context` event containing the model name.

**Rationale**:
- Some Codex sessions use the default model and record `NULL` in the database to save space.
- The model name is always recorded in the rollout file's first `turn_context` event.
- This two-step approach handles both cases without requiring all sessions to have model data stored in the database.

**Alternatives Considered**:
- Always read rollout files: Slower for sessions with model already in database; violates simplicity principle.
- Use a hardcoded default if NULL: Would mislead users about which model was actually used.

## User Message Count

**Decision**: For each session, open its rollout JSONL file, iterate through events, count `response_item` events where `role == "user"` and the message contains non-system text.

**Rationale**:
- The Codex database does not record user turn count directly.
- The rollout JSONL file records every user and assistant message in order, making an accurate count easy.
- This approach is consistent with message-counting logic for other platforms.

**Alternatives Considered**:
- Estimate from tokens: Inaccurate — token counts vary widely by model and content.
- Count all response_item events: Would double-count (includes assistant responses); filtering by role is required.

## Session Categorization & Character Classification

**Decision**: Apply the existing categorization and character classification logic (already implemented for Claude Code and Copilot) to Codex sessions without modification.

**Rationale**:
- The keyword-based categorization (Debugging, Code Generation, Planning, etc.) is model-agnostic and content-driven.
- Character classification (autonomous, deeply engaged, general) is based on message count and session duration, also content-agnostic.
- Reusing this logic ensures consistency across platforms and minimizes new code.

**Alternatives Considered**:
- Create Codex-specific categorization: Would fragment user experience and create maintenance burden.

## Platform Unification

**Decision**: Represent all Codex sessions under a single tool identifier `"codex"` in the data model and report. Store `source` (cli/vscode) as per-session metadata for detail views but do NOT split platform-level aggregates.

**Rationale**:
- Codex is a single product regardless of host (CLI or VS Code extension).
- Splitting by source would create confusion and duplicate data in platform-level charts.
- Per-session source metadata is useful for advanced users (detail views) but does not belong in aggregate charts.

**Alternatives Considered**:
- Create separate platform entries for "codex-cli" and "codex-vscode": Would bloat the report and mislead users (Codex is one product).

## Cost Estimation Omission

**Decision**: Omit cost estimates (input/output token split) for Codex. Display a dash (`—`) in cost columns and include an explanatory footnote.

**Rationale**:
- Codex database provides only a combined `tokens_used` total without input/output breakdown.
- Without the split, accurate pricing is impossible (Claude and Copilot models have different per-token costs for input vs. output).
- A dash is more honest than a guess; footnote explains the limitation.

**Alternatives Considered**:
- Assume 50/50 input/output split: Misleading and inaccurate for most real usage patterns.
- Display only combined cost: Would require reverse-engineering per-token rates, fragile and vendor-specific.

## Error Handling

**Decision**: If Codex database is missing, corrupted, or locked, log a warning and skip Codex ingestion. Report generation continues for other platforms.

**Rationale**:
- Codex is optional (not all users have it installed).
- Graceful degradation ensures users with only Claude Code or Copilot see a working report.
- Clear warning ensures users know if Codex data was skipped.

**Alternatives Considered**:
- Fail the entire report: Would punish users for a single optional platform being unavailable.
- Silently skip: Users would not know their Codex data was ignored.

## Eval Fixture Structure

**Decision**: Create synthetic Codex fixtures in `evals/fixtures/codex/` with:
- `state_1.sqlite` — SQLite database with a populated `threads` table (3+ sessions with varied data)
- `rollouts/` directory — JSONL files matching the rollout_path records in the database

**Rationale**:
- Mirrors the directory structure of real Codex installations.
- SQLite and JSONL are both human-readable with standard tools (sqlite3, jq).
- Allows evals to test the full ingestion pipeline without requiring real Codex usage.

**Alternatives Considered**:
- Use mocks/stubs: Would not test actual file I/O and parsing logic.
- Require real Codex data: Unfeasible in CI environments and unreliable across user machines.

## Implementation Phasing

**Decision**: This plan covers design only (research.md, data-model.md, contracts/, quickstart.md). Implementation will happen on a separate `004-codex-support-impl` branch after this spec branch is merged to `main`.

**Rationale**: Trunk-based development principle (v1.2.0) requires spec and implementation to be separate PRs. Design is reviewed and merged first; implementation follows on a fresh branch from `main`.
