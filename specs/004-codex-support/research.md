# Research: Codex Platform Support

**Feature**: 004-codex-support
**Date**: 2026-03-26

---

## Decision 1: Codex session database format

**Decision**: SQLite database at `~/.codex/state_N.sqlite`; primary table is `threads`.
**Rationale**: The OpenAI Codex CLI stores session history in a versioned SQLite file. The
version number N increments with schema migrations (e.g., `state_4.sqlite`, `state_5.sqlite`).
The highest-numbered file present is the active database.

**`threads` table columns** (confirmed from public Codex CLI source):

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT (UUID) | Session identifier — primary key |
| `created_at` | INTEGER | Unix timestamp (seconds) — session start |
| `updated_at` | INTEGER | Unix timestamp (seconds) — last update, used as session end |
| `cwd` | TEXT | Working directory at session start |
| `tokens_used` | INTEGER | Combined total tokens (input + output, no split) |
| `cli_version` | TEXT | Codex CLI version string (e.g., `"0.1.0"`) |
| `source` | TEXT | `"cli"` or `"vscode"` — session origin |
| `approval_mode` | TEXT | `"suggest"`, `"auto-edit"`, or `"full-auto"` |
| `rollout_path` | TEXT | Absolute path to the session's JSONL rollout file |
| `model` | TEXT | Model name; may be `NULL` if not persisted (resolved from rollout) |

**Alternatives considered**: Reading rollout JSONL files without the database — rejected;
requires directory scanning with no reliable mapping between files and session metadata.

---

## Decision 2: Rollout JSONL event format

**Decision**: Parse rollout JSONL files for model resolution (FR-003) and message counting (FR-004).
**Rationale**: The `threads` table `model` field is sometimes NULL for sessions where the model
was not yet persisted at session start. The rollout JSONL contains a `turn_context` event per
model invocation with the resolved model name.

**Relevant event shapes** (normalized across observed Codex CLI versions):

```jsonl
{"type": "session_meta", "data": {"sessionId": "...", "cwd": "..."}}
{"type": "turn_context", "data": {"model": "codex-mini-latest", "turnId": "..."}}
{"type": "response_item", "data": {"role": "user", "content": "fix the null check", "contentType": "text"}}
{"type": "response_item", "data": {"role": "assistant", "content": "...", "contentType": "text"}}
{"type": "event_msg", "data": {"event": "task_complete", "exitCode": 0}}
```

**Model resolution algorithm**:
1. If `threads.model` is non-null and non-empty → use it directly
2. Otherwise, open the rollout JSONL and scan for the first `turn_context` event
3. Extract `event["data"]["model"]` (or `event.get("model")` as fallback)
4. If rollout is missing or has no `turn_context` → `session.model = None`

**Message counting algorithm**:
1. Scan all `response_item` events in the rollout JSONL
2. Keep those where `data["role"] == "user"` (or `event["role"]`)
3. Filter out system messages using the existing `_is_system_message()` helper
4. `session.message_count = len(filtered_user_items)`

**Alternatives considered**: Counting rows in a separate `messages` table — the `threads`
table schema does not have a direct message count; rollout JSONL is the only source.

---

## Decision 3: Token data handling (no input/output split)

**Decision**: Store `threads.tokens_used` in `session.input_tokens`; set `session.output_tokens = None`.
**Rationale**: The Codex database provides only a combined token total. Storing it in
`input_tokens` re-uses the existing `Session` field without schema changes. `output_tokens = None`
acts as the signal that no split is available, which is already handled by `compute_session_costs()`
returning `None` cost when output tokens are absent. A small code change ensures Codex sessions
are explicitly skipped (cost = `None`), and the HTML renderer shows `—` for Codex cost columns.

**Alternatives considered**:
- Adding a new `total_tokens: Optional[int]` field to `Session` — cleaner semantically but adds
  a new field and requires touching all callsites; rejected per Simplicity principle.
- Splitting tokens 50/50 — rejected; factually incorrect and misleading.

---

## Decision 4: Eval fixture construction strategy

**Decision**: Construct SQLite fixture databases programmatically inside test `setUp()` using
Python `sqlite3` + `tempfile`. Rollout JSONL fixture files are committed as plain text.
**Rationale**: Binary SQLite files are opaque in git diffs and fragile to schema changes.
In-test construction keeps fixtures readable, always in sync with the schema, and consistent
with how the existing test suite constructs `Session` objects for edge-case coverage.
**Alternatives considered**: Pre-built `state_5.sqlite` binary committed to git — rejected;
opaque to reviewers. Mocking `sqlite3` — rejected; tests the mock, not the parser.

---

## Decision 5: `--codex-dir` CLI argument

**Decision**: Add `--codex-dir` argument to `generate_report.py` defaulting to `~/.codex/`.
**Rationale**: Follows the exact pattern of `--claude-dir`, `--vscode-dir`, `--copilot-cli-dir`.
Overridable for tests without any mocking. Consistent and zero-friction for end users.
**Alternatives considered**: Hard-coding `~/.codex/` and using monkeypatching in tests —
rejected; makes tests environment-dependent and fragile.
