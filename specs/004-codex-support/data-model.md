# Data Model: Codex Platform Support

## Entities

### CodexSession

A single Codex work session identified by a UUID.

**Fields**:
- `session_id` (string): Unique identifier (UUID from `threads.id`)
- `created_at` (ISO 8601 timestamp): Session start time
- `updated_at` (ISO 8601 timestamp): Session end time (derived from database record)
- `working_directory` (string): Directory where session was initiated
- `tokens_used` (integer): Combined input + output tokens for the session
- `model` (string or None): Active model name (resolved from thread record or rollout file)
- `cli_version` (string): Codex CLI version used
- `source` (enum: "cli" | "vscode"): Origin (terminal or IDE extension)
- `approval_mode` (string): Session collaboration mode (e.g., "agentic", "network-disabled")
- `first_user_message` (string): First user input; used as session title and for categorization
- `user_message_count` (integer): Total user-initiated messages in session
- `rollout_path` (string): Path to JSONL rollout file (for detail views)

**Validation Rules**:
- `session_id` must be a valid UUID
- `created_at` and `updated_at` must be valid ISO 8601 timestamps with `updated_at >= created_at`
- `tokens_used` must be a non-negative integer
- `cli_version` must be a valid version string (e.g., "1.2.3")
- `source` must be one of: "cli", "vscode"
- `user_message_count` must be a non-negative integer

**Relationships**:
- CodexSession → CodexRolloutFile (1:1, optional): Rollout file contains detailed events for the session

### CodexRolloutFile

A JSONL event log for a Codex session. Located at the path stored in `CodexSession.rollout_path`.

**Fields**:
- `path` (string): File path on disk
- `events` (array of objects): Ordered chronological events

**Event Types** (parsed from JSONL):
- `session_meta`: Session initialization metadata
- `turn_context`: Contains model name, token estimates, and other context for a turn
- `response_item`: User or assistant message; contains `role` and message text
- `event_msg`: Task lifecycle events (e.g., session start, completion)

**Validation Rules**:
- File must be readable and contain valid JSONL (one JSON object per line)
- Each event must have a `type` field
- `response_item` events must have `role` field (one of "user", "assistant")

### CodexSessionDatabase

SQLite database file at `~/.codex/state_N.sqlite` (N = highest version number).

**Schema** (primary table used):
- `threads` table: Canonical source for session summaries
  - Columns: `id` (TEXT), `created_at` (TEXT), `updated_at` (TEXT), `working_directory` (TEXT), `tokens_used` (INTEGER), `model` (TEXT), `cli_version` (TEXT), `source` (TEXT), `approval_mode` (TEXT), `rollout_path` (TEXT)

**Discovery Logic**:
- Search `~/.codex/` for files matching pattern `state_*.sqlite`
- Use the highest-numbered version (e.g., prefer `state_5.sqlite` over `state_4.sqlite`)

## Data Flow

```
~/.codex/state_N.sqlite
    ↓
[Read threads table]
    ↓
[For each thread: extract session metadata]
    ↓
[For each thread with model == NULL: open rollout file, find model in turn_context]
    ↓
[For each thread: count user messages in rollout JSONL]
    ↓
[Apply categorization & character classification (reuse existing logic)]
    ↓
CodexSession objects → merged into report data structures
```

## Integration with Existing Data Structures

Codex sessions are merged into the same aggregated structures used for Claude Code and Copilot:

- **sessions[]**: Added to the global sessions array with `tool = "codex"`
- **platform_stats**: Added to platform breakdown (sessions, tokens, session_count by category)
- **activity_timeline**: Codex activity plotted on the same timeline as other platforms
- **category_distribution**: Codex sessions categorized using existing keywords (Debugging, Code Generation, etc.)
- **character_distribution**: Codex sessions classified using existing criteria (autonomous, deeply engaged, general)

**Metadata Stored Separately**:
- `source` (cli/vscode) is stored per-session but NOT used to split platform-level aggregates
- `approval_mode` is available for per-session detail views but not aggregated in charts

## Cost Representation

Codex sessions do NOT contribute to cost calculations. Cost columns display `—` (dash) for all Codex sessions. A footnote explains: "Cost estimates not available for Codex. The session database provides only combined token totals without input/output breakdown."

## Error Handling

**Missing Database**:
- If `~/.codex/` does not exist or contains no `state_*.sqlite` files, log an info-level message ("Codex database not found; skipping Codex ingestion") and proceed with report generation using other platforms.

**Corrupted Database**:
- If database is not a valid SQLite file or the `threads` table is missing, log a warning and skip Codex ingestion.

**Locked Database**:
- If database is locked by another process, log a warning and skip Codex ingestion.

**Missing Rollout File**:
- If a session record points to a rollout file that does not exist, log a warning and use available metadata (skip model resolution and message count for that session).

**Malformed Rollout JSONL**:
- If a rollout file is not valid JSONL or contains unexpected event structures, log a warning and skip detailed parsing for that session (use database metadata only).

## Backward Compatibility

The existing data structures for Claude Code and Copilot sessions remain unchanged. Codex sessions are added as a new tool source alongside existing ones. No breaking changes to the report schema.

## Forward Compatibility

If Codex database schema evolves (e.g., `state_6.sqlite` with new columns), the parser will:
- Read only the columns it knows about (ignores new columns)
- Skip any new required fields and log a warning if data is incomplete
- Continue processing with available data

This ensures reports remain usable even if the Codex database schema changes.
