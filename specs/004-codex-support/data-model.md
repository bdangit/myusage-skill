# Data Model: Codex Platform Support

**Feature**: 004-codex-support
**Date**: 2026-03-26

---

## Codex Session Database (`~/.codex/state_N.sqlite`)

### Database Discovery

```python
import glob, os, re

def _find_codex_db(codex_dir: str) -> Optional[str]:
    """Return path to the highest-versioned state_N.sqlite, or None."""
    codex_dir = os.path.expanduser(codex_dir)
    if not os.path.isdir(codex_dir):
        return None
    pattern = os.path.join(codex_dir, "state_*.sqlite")
    candidates = glob.glob(pattern)
    if not candidates:
        return None
    def version_key(p: str) -> int:
        m = re.search(r"state_(\d+)\.sqlite$", p)
        return int(m.group(1)) if m else 0
    return max(candidates, key=version_key)
```

### `threads` Table Schema

```sql
CREATE TABLE threads (
    id           TEXT PRIMARY KEY,   -- UUID, e.g. "a1b2c3d4-..."
    created_at   INTEGER NOT NULL,   -- Unix seconds — session start time
    updated_at   INTEGER NOT NULL,   -- Unix seconds — session end time
    cwd          TEXT,               -- Working directory path
    tokens_used  INTEGER,            -- Combined total (input + output, no split)
    cli_version  TEXT,               -- e.g. "0.1.0"
    source       TEXT,               -- "cli" | "vscode"
    approval_mode TEXT,              -- "suggest" | "auto-edit" | "full-auto"
    rollout_path TEXT,               -- Absolute path to rollout JSONL file
    model        TEXT                -- Model name; may be NULL
);
```

### SQL Query

```sql
SELECT id, created_at, updated_at, cwd, tokens_used,
       cli_version, source, approval_mode, rollout_path, model
FROM threads
ORDER BY created_at ASC;
```

---

## Rollout JSONL File

Located at the path stored in `threads.rollout_path`. Contains ordered JSONL events.

### Relevant Event Types

| Type | Purpose | Key Fields |
|------|---------|-----------|
| `session_meta` | Session metadata | `data.sessionId`, `data.cwd` |
| `turn_context` | Model invocation start | `data.model` — used for model resolution |
| `response_item` | User or assistant message | `data.role`, `data.content`, `data.contentType` |
| `event_msg` | Task lifecycle | `data.event` — e.g. `"task_complete"` |

### Sample Events

```jsonl
{"type": "session_meta", "data": {"sessionId": "a1b2c3d4-...", "cwd": "/home/user/project"}}
{"type": "turn_context", "data": {"model": "codex-mini-latest", "turnId": "turn-001"}}
{"type": "response_item", "data": {"role": "user", "content": "add error handling", "contentType": "text"}}
{"type": "response_item", "data": {"role": "assistant", "content": "I'll add try/except...", "contentType": "text"}}
{"type": "event_msg", "data": {"event": "task_complete", "exitCode": 0}}
```

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
| `updated_at` | `end_time` | `datetime.fromtimestamp(updated_at, tz=timezone.utc)` |
| `cwd` | `project_path` | May be `None` |
| `tokens_used` | `input_tokens` | Combined total stored here; `output_tokens = None` |
| `source` | `codex_source` | `"cli"` or `"vscode"` |
| `approval_mode` | `mode` | Stored as-is (`"suggest"` / `"auto-edit"` / `"full-auto"`) |
| `model` (or rollout) | `model` | Null-coalesced from DB then rollout JSONL |
| `rollout_path` | *(internal)* | Used during parsing; not stored on Session |
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
    ├── session-codex-001.jsonl   # 2 user messages; model in DB
    ├── session-codex-002.jsonl   # 3 user messages; model from rollout (DB model=NULL)
    └── session-codex-003.jsonl   # 1 user message; source="vscode"
```

The SQLite `state_5.sqlite` fixture is constructed in test `setUp()` using Python `sqlite3`.
Each test that requires the database creates it in a `tempfile.mkdtemp()` and tears it down
in `tearDown()`. The rollout JSONL files in `evals/fixtures/codex/rollouts/` are read by the
parser at the rollout_path stored in the constructed database.

---

## Report Display: Cost Columns

Codex sessions have `estimated_cost_usd = None` and `output_tokens = None`. The HTML renderer
detects `session.tool == "codex"` (or `output_tokens is None` without `input_tokens is None`)
and renders:

- Cost cell: `—`
- Token display: combined total from `input_tokens` with label `"tokens (combined)"`
- Footnote: `"* Codex cost unavailable — session database provides only a combined token total with no input/output breakdown."`
