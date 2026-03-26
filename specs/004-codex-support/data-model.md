# Data Model: Codex Platform Support

**Feature**: 004-codex-support
**Date**: 2026-03-26

---

## Codex Session Database (`~/.codex/state_5.sqlite`)

### `threads` table — columns used by the parser

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | TEXT | No | UUID — used as `Session.session_id` |
| `created_at` | INTEGER | No | Unix seconds UTC — `Session.start_time` |
| `updated_at` | INTEGER | No | Unix seconds UTC — `Session.end_time` |
| `cwd` | TEXT | No | Working directory — `Session.project_path` |
| `tokens_used` | INTEGER | No | Combined total tokens — `Session.total_tokens` |
| `cli_version` | TEXT | No | CLI version string (metadata only) |
| `source` | TEXT | No | `"cli"` \| `"vscode"` \| `"exec"` \| `"mcp"` — stored per-session |
| `approval_mode` | TEXT | No | `"on-request"` \| `"never"` \| `"untrusted"` \| `"granular"` |
| `model` | TEXT | **Yes** | Model name — nullable; fall back to rollout JSONL if NULL |
| `rollout_path` | TEXT | No | Absolute path to the session's JSONL rollout file |
| `first_user_message` | TEXT | No | Auto-populated title — used as session category input |
| `archived` | INTEGER | No | `0` or `1` — skip archived sessions |

**Query**: `SELECT id, created_at, updated_at, cwd, tokens_used, cli_version, source, approval_mode, model, rollout_path, first_user_message FROM threads WHERE archived = 0`

---

## Rollout JSONL File Format

Each line is a JSON object: `{ "timestamp": "<ISO8601Z>", "type": "<variant>", "payload": { ... } }`.

### Events used by the parser

#### `session_meta`
```json
{
  "timestamp": "2026-01-15T09:00:00Z",
  "type": "session_meta",
  "payload": {
    "id": "5973b6c0-...",
    "cwd": "/home/user/project",
    "source": "cli",
    "cli_version": "1.2.3"
  }
}
```
_Used for: cross-validation only (primary fields come from SQLite)_

#### `turn_context`
```json
{
  "timestamp": "2026-01-15T09:00:01Z",
  "type": "turn_context",
  "payload": {
    "turn_id": "...",
    "model": "codex-mini-latest",
    "approval_policy": "on-request"
  }
}
```
_Used for: model name fallback when `threads.model IS NULL` (FR-003)_

#### `response_item`
```json
{
  "timestamp": "2026-01-15T09:00:30Z",
  "type": "response_item",
  "payload": {
    "role": "user",
    "content": [{ "type": "input_text", "text": "Fix the authentication bug" }]
  }
}
```
_Used for: user turn counting (FR-004) and category classification (FR-006)_

Content items with text enclosed in angle-bracket XML-style tags (e.g., `<user_instructions>`, `<environment_context>`) are treated as system-injected messages and excluded from user turn counts.

---

## Session Dataclass Extension

One new field added to `Session`:

```python
total_tokens: Optional[int] = None   # Codex: combined tokens_used; None for all other tools
```

**Mapping for Codex sessions**:

| `Session` field | Source |
|----------------|--------|
| `session_id` | `threads.id` |
| `tool` | `"codex"` (constant) |
| `project_path` | `threads.cwd` |
| `start_time` | `datetime.fromtimestamp(threads.created_at, tz=timezone.utc)` |
| `end_time` | `datetime.fromtimestamp(threads.updated_at, tz=timezone.utc)` |
| `duration_seconds` | `(end_time - start_time).total_seconds()` |
| `messages` | Built from `response_item` events in rollout JSONL |
| `message_count` | Count of non-system `response_item` events with `role == "user"` |
| `model` | `threads.model` if non-NULL, else first `turn_context.payload.model` in rollout |
| `mode` | `threads.approval_mode` (mapped to canonical mode string) |
| `input_tokens` | `None` |
| `output_tokens` | `None` |
| `total_tokens` | `threads.tokens_used` |
| `tool_call_count` | `0` (not available from Codex data) |
| `character_approximate` | `True` (no tool_call_count available) |
| `session_character` | Derived by `classify_session_character()` with approximate logic |
| `category` | Derived by `categorize_session()` using first user message from rollout |

---

## Approval Mode → Canonical Mode Mapping

| `threads.approval_mode` | `Session.mode` |
|------------------------|----------------|
| `"on-request"` | `"default"` |
| `"never"` | `"auto"` |
| `"untrusted"` | `"cautious"` |
| `"granular"` | `"granular"` |
| anything else | `None` |

---

## Fixture Schema

Fixtures live in `evals/fixtures/codex/` and mirror the real Codex storage layout:

```text
evals/fixtures/codex/
├── state_5.sqlite               # SQLite DB with 3+ thread rows (rollout_path uses placeholder)
└── sessions/
    ├── rollout-sess-001.jsonl   # Debugging session fixture (EVAL-003)
    ├── rollout-sess-002.jsonl   # Code Generation session (EVAL-003)
    └── rollout-sess-003.jsonl   # NULL model session (EVAL-004)
```

Test setup rewrites `rollout_path` values in a temp copy of `state_5.sqlite` to absolute paths
pointing to `evals/fixtures/codex/sessions/` before running the parser.

---

## Report Display Changes

### TOOL_LABELS addition

```python
TOOL_LABELS["codex"] = "Codex"
```

### ACCENT_COLORS addition

```python
ACCENT_COLORS["codex"] = "#f97316"   # orange (distinct from existing purple/blue/green)
```

### Cost display (FR-012)

For sessions where `s.tool == "codex"`:
- `effective_prus` remains `None`
- `estimated_cost_usd` remains `None`
- HTML cost cell renders `—`
- A footnote below the cost table reads: *"Codex cost estimates are not available — the Codex session database provides only a combined token total without an input/output breakdown required for pricing."*

### Token display

Existing per-tool token display logic (`input_tokens`, `output_tokens`) gains a Codex branch:
- If `snap.total_input_tokens is None and snap.total_output_tokens is None` and the tool is `"codex"`:
  - Render a single "Tokens (total)" column with `sum(s.total_tokens for s in snap.sessions if s.total_tokens is not None)`
  - Standard Input/Output columns show `—`
