# Research: Codex Platform Support

**Feature**: 004-codex-support
**Date**: 2026-03-26

---

## Decision 1: Codex session database format

**Decision**: SQLite database at `~/.codex/state_5.sqlite`; primary table is `threads`.
**Rationale**: The OpenAI Codex CLI stores session history in a versioned SQLite file named
`state_{STATE_DB_VERSION}.sqlite`. As of the current Codex CLI release (`@openai/codex@0.116.0`
and `codex-rs/state/src/lib.rs`), `STATE_DB_VERSION = 5`, so the active file is `state_5.sqlite`.
SQLx migrations inside the binary manage schema evolution transparently; the version constant
controls which numbered file is active (older numbered files are deleted on startup).

> **Source**: Schema verified live from the public `openai/codex` repository
> (`codex-rs/state/migrations/0001_threads.sql` through `0022_*`, commit `4b50446`)
> and `codex-rs/state/src/lib.rs` (STATE_DB_VERSION constant) and
> `codex-rs/state/src/model/thread_metadata.rs` (ThreadRow struct).
> I did NOT install the Codex binary — I used the GitHub MCP tool to read the source.
> Earlier spec drafts used LLM training knowledge; this version is verified from source.

**`threads` table — full schema after all migrations (0001–0022)**:

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | TEXT | NOT NULL PK | UUID session identifier |
| `rollout_path` | TEXT | NOT NULL | Absolute path to rollout JSONL file |
| `created_at` | INTEGER | NOT NULL | Unix seconds — session start |
| `updated_at` | INTEGER | NOT NULL | Unix seconds — last activity |
| `source` | TEXT | NOT NULL | Session origin: `"cli"`, `"vscode"`, `"exec"`, `"mcp"`, `"unknown"`, `"subagent_*"` |
| `model_provider` | TEXT | NOT NULL | Provider identifier, e.g. `"openai"` |
| `cwd` | TEXT | NOT NULL | Working directory at session start |
| `title` | TEXT | NOT NULL | Best-effort session title (from first user message) |
| `sandbox_policy` | TEXT | NOT NULL | e.g. `"read-only"`, `"danger-full-access"` (kebab-case) |
| `approval_mode` | TEXT | NOT NULL | `"on-request"` (default), `"never"`, `"on-failure"`, `"untrusted"` (kebab-case enum) |
| `tokens_used` | INTEGER | NOT NULL DEFAULT 0 | Combined total tokens (input + output, no split) |
| `has_user_event` | INTEGER | NOT NULL DEFAULT 0 | 1 if session has a user message event |
| `archived` | INTEGER | NOT NULL DEFAULT 0 | 1 if archived |
| `archived_at` | INTEGER | NULL | Unix seconds — archive timestamp |
| `git_sha` | TEXT | NULL | Git commit SHA if known |
| `git_branch` | TEXT | NULL | Git branch if known |
| `git_origin_url` | TEXT | NULL | Git remote URL if known |
| `cli_version` | TEXT | NOT NULL DEFAULT `''` | CLI version string (migration 0005) |
| `first_user_message` | TEXT | NOT NULL DEFAULT `''` | First user message text (migration 0007) |
| `agent_nickname` | TEXT | NULL | Sub-agent nickname (migration 0013) |
| `agent_role` | TEXT | NULL | Sub-agent role (migration 0013) |
| `model` | TEXT | NULL | Model name; NULL until set from TurnContext (migration 0020) |
| `reasoning_effort` | TEXT | NULL | Reasoning effort string (migration 0020) |
| `agent_path` | TEXT | NULL | Agent path (migration 0022) |

**Key fields for the parser**:
- `source`: identifies session origin (CLI vs VS Code)
- `first_user_message`: populated directly from the rollout — **use this for session categorization; no need to read the rollout JSONL for categorization**
- `model`: nullable — fall back to rollout JSONL `TurnContextItem.model` when NULL
- `tokens_used`: combined total — no split available (see Decision 3)

**Alternatives considered**: Reading rollout JSONL files without the database — rejected;
requires directory scanning with no reliable mapping between files and session metadata.

---

## Decision 2: Rollout JSONL event format

**Decision**: Parse rollout JSONL files for (1) model resolution when `threads.model` is NULL, and (2) user message counting (FR-004). The `first_user_message` column in the DB is used for session categorization — the rollout JSONL is NOT needed for that purpose.
**Rationale**: The `threads` table `model` field (added in migration 0020) is sometimes NULL for
sessions created before that migration or sessions where model was not persisted. The rollout
JSONL contains a `TurnContextItem` event per model invocation with the resolved model name.
`first_user_message` is populated directly in the DB from rollout metadata during indexing
(migration 0007 + `apply_event_msg` in `extract.rs`); using it avoids an extra rollout read for categorization.

> **Source**: `codex-rs/state/src/extract.rs` (rollout item types, apply functions),
> `codex-rs/protocol/src/protocol.rs` (RolloutItem, SessionSource, AskForApproval enum definitions)

**Relevant rollout item types** (from `RolloutItem` enum in `codex_protocol`):

```jsonl
{"type": "session_meta", "meta": {"id": "...", "source": "cli", "cwd": "...", "cli_version": "..."}}
{"type": "turn_context", "cwd": "...", "model": "codex-mini-latest", "approval_policy": "on-request", "sandbox_policy": "read-only"}
{"type": "event_msg", "event": {"type": "user_message", "message": "\u001b]133;A\u001b\\ actual user request"}}
{"type": "response_item", "role": "user", "content": [{"type": "input_text", "text": "fix the null check"}]}
{"type": "response_item", "role": "assistant", "content": [...]}
{"type": "event_msg", "event": {"type": "token_count", "info": {"total_token_usage": {"total_tokens": 1200}}}}
```

**Model resolution algorithm**:
1. If `threads.model` is non-null and non-empty → use it directly (common case after migration 0020)
2. Otherwise, open the rollout JSONL and scan for the first `turn_context` line
3. Extract the `model` field from the `TurnContextItem`
4. If rollout is missing or has no `turn_context` → `session.model = None`

**Message counting algorithm**:
1. Scan all `response_item` lines in the rollout JSONL
2. Keep those where `role == "user"`
3. Filter out system messages using the existing `_is_system_message()` helper
4. `session.message_count = len(filtered_user_items)`

**Alternatives considered**: Counting from `EventMsg::UserMessage` events — those are used for `first_user_message`/`title` in the DB but do NOT produce `response_item` rows that feed `message_count` (confirmed from `apply_response_item` which is a no-op for metadata).

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

---

## Decision 6: DB file discovery

**Decision**: Look for `state_5.sqlite` by name in `codex_dir`, with a glob fallback to
`state_*.sqlite` if the exact name is not found. Pick the highest-versioned file.
**Rationale**: `STATE_DB_VERSION` is a constant in the compiled binary. Verified as `5`
from `codex-rs/state/src/lib.rs`. Older versioned files are deleted by the CLI on startup,
so in practice only one `state_N.sqlite` file will exist. The glob fallback handles future
version bumps gracefully without requiring a spec update.
**Source**: `codex-rs/state/src/lib.rs` (`STATE_DB_FILENAME = "state"`, `STATE_DB_VERSION = 5`),
`codex-rs/state/src/runtime.rs` (`state_db_filename()`, `remove_legacy_db_files()`).
