# Contract: parse_codex()

**Type**: Internal parser function
**Purpose**: Read Codex session data from the local SQLite database and associated JSONL rollout
files; return `List[Session]` using the same `Session` dataclass as other parsers.

## Signature

```python
def parse_codex(codex_dir: str) -> List[Session]:
    ...
```

## Inputs

| Parameter | Type | Default (CLI) | Description |
|-----------|------|---------------|-------------|
| `codex_dir` | `str` | `~/.codex` | Root directory for Codex data. Tilde-expanded. |

## Outputs

| Return | Description |
|--------|-------------|
| `List[Session]` | Zero or more sessions. Empty list if `codex_dir` does not exist, no `state_N.sqlite` is found, database is locked, or all threads are archived. |

## Behaviour

### Database discovery

1. Tilde-expand `codex_dir`
2. If directory does not exist → return `[]`
3. Glob `{codex_dir}/state_*.sqlite`; extract integer N from each filename
4. If no matches → return `[]` (Codex not installed or no database yet)
5. Open the file with the highest N using `sqlite3.connect(..., check_same_thread=False)`
6. On `sqlite3.OperationalError` (locked, corrupt) → print warning to stderr, return `[]`

### Session query

```sql
SELECT id, created_at, updated_at, cwd, tokens_used, cli_version, source,
       approval_mode, model, rollout_path, first_user_message
FROM threads
WHERE archived = 0
```

### Per-session processing

For each row:

1. **Timestamps**: `datetime.fromtimestamp(created_at, tz=timezone.utc)` for start; same for `updated_at` as end.
2. **Model**: Use `threads.model` if non-NULL and non-empty; otherwise open `rollout_path` and read the first `turn_context` event's `payload.model`.
3. **User turn count and messages**: Open `rollout_path`; parse each line as JSON; collect `response_item` events where `payload.role == "user"` and content text is non-empty and does not match `_is_system_message()`. Build `Message` objects from these events with `role="user"`.
4. **Missing rollout file**: If `rollout_path` does not exist or cannot be read → fall back to `first_user_message` as a single synthetic Message; set `message_count = 1`; model remains `threads.model` or `None`.
5. **Session character**: Call `classify_session_character()` with `character_approximate=True` (tool_call_count is not available).
6. **Category**: Call `categorize_session()` using the messages built above.
7. **Tokens**: Set `total_tokens = threads.tokens_used`, `input_tokens = None`, `output_tokens = None`.
8. **Inter-message gaps**: Computed from sorted Message timestamps if ≥2 messages; else `[]`.
9. **Skip if zero messages**: If no messages can be constructed (empty rollout + empty `first_user_message`) → skip session.

### Session fields

| Field | Value |
|-------|-------|
| `session_id` | `threads.id` |
| `tool` | `"codex"` |
| `project_path` | `threads.cwd` or `None` if empty string |
| `mode` | Mapped from `threads.approval_mode` (see data-model.md) |
| `character_approximate` | `True` |
| `model_request_counts` | `None` |
| `model_token_totals` | `None` |
| `effective_prus` | `None` |
| `estimated_cost_usd` | `None` |

## Error Handling

| Condition | Behaviour |
|-----------|-----------|
| `codex_dir` does not exist | Return `[]` silently |
| No `state_N.sqlite` found | Return `[]` silently |
| Database locked / corrupt | Print warning to stderr, return `[]` |
| `rollout_path` missing or unreadable | Print warning to stderr, use `first_user_message` fallback |
| Malformed JSON line in rollout JSONL | Print warning to stderr, skip that line |
| `created_at == updated_at` | Duration = 0.0 seconds (valid edge case) |

## Integration in `main()`

```python
# --- Codex ---
codex_dir_display = args.codex_dir
print(f"Scanning Codex history: {codex_dir_display} ...", end=" ", flush=True, file=sys.stderr)
try:
    codex_sessions = parse_codex(args.codex_dir)
except Exception as exc:
    print(f"\nError: {exc}", file=sys.stderr)
    sys.exit(2)
if cutoff:
    codex_sessions = [s for s in codex_sessions if s.start_time >= cutoff]
print(f"{len(codex_sessions)} sessions found", file=sys.stderr)
all_sessions.extend(codex_sessions)
```

## CLI argument

```python
parser.add_argument(
    "--codex-dir",
    default="~/.codex",
    help="Override Codex data directory (default: ~/.codex)",
)
```
