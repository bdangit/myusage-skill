# Data Model: Codex Platform Support

**Feature**: 004-codex-support
**Date**: 2026-03-26

---

## Codex Session Database (`~/.codex/state_5.sqlite`)

### Database Discovery

> **Verified**: `STATE_DB_VERSION = 5` from `codex-rs/state/src/lib.rs` (commit `4b50446`).
> The glob fallback handles future version bumps.

```python
import glob, os, re
from typing import Optional

def _find_codex_db(codex_dir: str) -> Optional[str]:
    """Return path to the active state_N.sqlite, or None."""
    codex_dir = os.path.expanduser(codex_dir)
    if not os.path.isdir(codex_dir):
        return None
    # Prefer the known current version first
    exact = os.path.join(codex_dir, "state_5.sqlite")
    if os.path.isfile(exact):
        return exact
    # Fallback: pick highest-versioned file present
    pattern = os.path.join(codex_dir, "state_*.sqlite")
    candidates = glob.glob(pattern)
    if not candidates:
        return None
    def version_key(p: str) -> int:
        m = re.search(r"state_(\d+)\.sqlite$", p)
        return int(m.group(1)) if m else 0
    return max(candidates, key=version_key)
```

### `threads` Table — Verified Schema

> **Source**: `codex-rs/state/migrations/0001_threads.sql` through `0022_*`
> and `codex-rs/state/src/model/thread_metadata.rs` (`ThreadRow` struct), commit `4b50446`.

```sql
-- From migration 0001 (base schema)
CREATE TABLE threads (
    id           TEXT PRIMARY KEY,   -- UUID, e.g. "a1b2c3d4-..."
    rollout_path TEXT NOT NULL,      -- Absolute path to rollout JSONL file
    created_at   INTEGER NOT NULL,   -- Unix seconds — session start time
    updated_at   INTEGER NOT NULL,   -- Unix seconds — last activity time
    source       TEXT NOT NULL,      -- "cli" | "vscode" | "exec" | "mcp" | "unknown" | "subagent_*"
    model_provider TEXT NOT NULL,    -- e.g. "openai"
    cwd          TEXT NOT NULL,      -- Working directory path
    title        TEXT NOT NULL,      -- Best-effort session title (from first user message)
    sandbox_policy TEXT NOT NULL,    -- e.g. "read-only" (kebab-case)
    approval_mode TEXT NOT NULL,     -- "on-request" | "never" | "on-failure" | "untrusted" (kebab-case)
    tokens_used  INTEGER NOT NULL DEFAULT 0,  -- Combined total (input + output, no split)
    has_user_event INTEGER NOT NULL DEFAULT 0,
    archived     INTEGER NOT NULL DEFAULT 0,
    archived_at  INTEGER,            -- Unix seconds — archive time
    git_sha      TEXT,               -- Git commit SHA if known
    git_branch   TEXT,               -- Git branch if known
    git_origin_url TEXT,             -- Git remote URL if known
    -- Added by subsequent migrations:
    cli_version  TEXT NOT NULL DEFAULT '',    -- CLI version, e.g. "0.116.0" (migration 0005)
    first_user_message TEXT NOT NULL DEFAULT '',  -- First user message text (migration 0007)
    agent_nickname TEXT,             -- Sub-agent nickname (migration 0013)
    agent_role   TEXT,               -- Sub-agent role (migration 0013)
    model        TEXT,               -- Model name; NULL until set from TurnContext (migration 0020)
    reasoning_effort TEXT,           -- Reasoning effort string (migration 0020)
    agent_path   TEXT                -- Agent path (migration 0022)
);
```

### SQL Query

```sql
SELECT id, rollout_path, created_at, updated_at, source,
       cwd, tokens_used, first_user_message, model, approval_mode
FROM threads
WHERE archived = 0
ORDER BY created_at ASC;
```

Note: `WHERE archived = 0` — archived sessions are user-intentionally hidden; skip them.

---

## Rollout JSONL File

Located at the path stored in `threads.rollout_path`. Contains ordered JSONL events.

> **Source**: `codex-rs/state/src/extract.rs` (apply functions),
> `codex-rs/protocol/src/protocol.rs` (RolloutItem enum)

### Relevant Event Types

| Type | Purpose | Key Fields |
|------|---------|-----------|
| `session_meta` | Session metadata | `meta.id`, `meta.source`, `meta.cwd`, `meta.cli_version` |
| `turn_context` | Model invocation | `model` — used for model resolution when DB `model` is NULL |
| `response_item` | User or assistant message | `role`, `content` (array) |
| `event_msg` | Lifecycle events | `event.type`: `"user_message"`, `"token_count"`, etc. |

### Sample Events (real format from codex-protocol)

```jsonl
{"type":"session_meta","meta":{"id":"a1b2c3d4-...","source":"cli","cwd":"/home/user/project","cli_version":"0.116.0","originator":"codex_cli_rs"}}
{"type":"turn_context","cwd":"/home/user/project","model":"codex-mini-latest","approval_policy":"on-request","sandbox_policy":"read-only"}
{"type":"event_msg","event":{"type":"user_message","message":"\u001b]133;A\u001b\\ add error handling"}}
{"type":"response_item","role":"user","content":[{"type":"input_text","text":"add error handling"}]}
{"type":"response_item","role":"assistant","content":[{"type":"text","text":"I'll add try/except..."}]}
{"type":"event_msg","event":{"type":"token_count","info":{"total_token_usage":{"total_tokens":1840}}}}
```

### Important

- `first_user_message` is already in the `threads` DB row (migration 0007) — **use it directly for `categorize_session()`; do NOT read rollout JSONL for this**
- `model` resolution from rollout: scan for first `turn_context` line and read its `model` field
- Message counting: scan `response_item` lines where `role == "user"`, filter system messages

---

## Session Dataclass Extension

One new field is added to the existing `Session` dataclass in `generate_report.py`:

```python
@dataclass
class Session:
    # ... existing fields unchanged ...
    codex_source: Optional[str] = None   # "cli" or "vscode" — Codex sessions only
```

### Codex-to-Session Field Mapping

| `threads` column | `Session` field | Notes |
|-----------------|----------------|-------|
| `id` | `session_id` | UUID string |
| `created_at` | `start_time` | `datetime.fromtimestamp(created_at, tz=timezone.utc)` |
| `updated_at` | `end_time` | `datetime.fromtimestamp(updated_at, tz=timezone.utc)` — clamp to start_time if earlier |
| `cwd` | `project_path` | Always present (NOT NULL) |
| `tokens_used` | `input_tokens` | Combined total stored here; `output_tokens = None` |
| `source` | `codex_source` | `"cli"` or `"vscode"` (other values stored as-is) |
| `approval_mode` | `mode` | `"on-request"` / `"never"` / `"on-failure"` / `"untrusted"` (kebab-case) |
| `first_user_message` | *(categorization)* | Non-empty → construct a synthetic `Message` and pass to `categorize_session()`; not stored separately |
| `model` (or rollout) | `model` | Use DB value if non-NULL/non-empty; otherwise scan rollout `turn_context` |
| `rollout_path` | *(internal)* | Used for message counting and model fallback only |
| *(rollout count)* | `message_count` | Count of non-system user `response_item` events |
| *(rollout msgs)* | `messages` | `Message` objects for user `response_item` events |
| n/a | `tool` | Always `"codex"` |
| n/a | `estimated_cost_usd` | Always `None` (no input/output split) |
| n/a | `effective_prus` | Always `None` (not a Copilot session) |

---

## Eval Fixture Layout

```text
evals/fixtures/codex/
└── rollouts/
    ├── session-codex-001.jsonl   # 2 user response_items; model in DB; first_user_message in DB
    ├── session-codex-002.jsonl   # 3 user response_items; turn_context with model="o3" (DB model=NULL)
    └── session-codex-003.jsonl   # 1 user response_item; source="vscode" in DB
```

The SQLite `state_5.sqlite` fixture database is constructed in test `setUp()` using Python `sqlite3`.
Each test creates a `state_5.sqlite` in a `tempfile.mkdtemp()` with the correct schema columns
matching the real Codex DB (from the verified migration SQL above) and tears it down in `tearDown()`.
Rollout JSONL fixture files live at committed paths; the DB rows reference absolute paths
constructed at test time using the `evals/fixtures/codex/rollouts/` directory.

---

## Report Display: Cost Columns

Codex sessions have `estimated_cost_usd = None` and `output_tokens = None`. The HTML renderer
detects `session.tool == "codex"` (or `output_tokens is None` without `input_tokens is None`)
and renders:

- Cost cell: `—`
- Token display: combined total from `input_tokens` with label `"tokens (combined)"`
- Footnote: `"* Codex cost unavailable — session database provides only a combined token total with no input/output breakdown."`
