# Contract: `parse_codex(codex_dir: str) -> List[Session]`

**Type**: Python function (internal parser)
**Module**: `skills/myusage/scripts/generate_report.py`
**Purpose**: Parse all Codex sessions from the local Codex database and return them as
`Session` objects compatible with the rest of the report pipeline.

---

## Signature

```python
def parse_codex(codex_dir: str) -> List[Session]:
    ...
```

---

## Arguments

| Argument | Type | Default (in `main()`) | Description |
|----------|------|-----------------------|-------------|
| `codex_dir` | `str` | `"~/.codex/"` | Directory containing `state_N.sqlite` files. Tilde-expanded internally. |

---

## Return value

`List[Session]` — zero or more `Session` objects. Returns `[]` (empty list) whenever:
- `codex_dir` does not exist or is not a directory
- No `state_*.sqlite` files are found in `codex_dir`
- The SQLite file is present but contains zero rows in `threads`
- The SQLite file is locked, corrupt, or inaccessible

**Never raises** — all errors are caught and printed to `stderr` as warnings, then execution
continues with the sessions collected so far.

---

## Session field contract

For every `Session` object returned:

| Field | Guarantee |
|-------|-----------|
| `tool` | Always `"codex"` |
| `session_id` | Non-empty string (UUID from `threads.id`) |
| `start_time` | UTC-aware `datetime` from `threads.created_at` |
| `end_time` | UTC-aware `datetime` from `threads.updated_at`; always ≥ `start_time` |
| `duration_seconds` | `(end_time - start_time).total_seconds()` — may be `0.0` |
| `project_path` | String or `None` |
| `model` | String (from DB or rollout JSONL) or `None` if unresolvable |
| `mode` | `"suggest"`, `"auto-edit"`, `"full-auto"`, or `None` |
| `codex_source` | `"cli"`, `"vscode"`, or `None` |
| `message_count` | `>= 0`; count of non-system user `response_item` events in rollout |
| `messages` | `List[Message]` for user `response_item` events (may be empty) |
| `input_tokens` | Combined `tokens_used` integer, or `None` if column is NULL |
| `output_tokens` | Always `None` (no split available) |
| `effective_prus` | Always `None` |
| `estimated_cost_usd` | Always `None` |
| `session_character` | Set by `classify_session_character()` after parsing |
| `category` | Set by `categorize_session()` after parsing |

---

## Error handling

| Condition | Behaviour |
|-----------|-----------|
| `codex_dir` absent | Return `[]` silently (no warning needed — normal for users without Codex) |
| No `state_*.sqlite` found | Return `[]` silently |
| `sqlite3.OperationalError` on open/query | Print `Warning: ...` to stderr; return sessions collected so far |
| Rollout JSONL missing or unreadable | Print `Warning: ...` to stderr; session is still emitted with `model=None` and `message_count=0` |
| Malformed JSON line in rollout | Print `Warning: ...` to stderr; skip that line; continue |
| `threads.updated_at < threads.created_at` | Clamp `end_time = start_time`; `duration_seconds = 0.0` |

---

## Integration points

- Called in `main()` alongside `parse_claude_code()`, `parse_copilot_vscode()`, `parse_copilot_cli()`
- Sessions fed into `build_report()` → `compute_session_costs()` → `render_html()`
- `compute_session_costs()` MUST skip Codex sessions (leave `estimated_cost_usd = None`)
- HTML renderer checks `session.tool == "codex"` to display `—` in cost columns

---

## CLI argument

```
--codex-dir PATH    Directory containing Codex state_N.sqlite files.
                    Default: ~/.codex/
```

Added to the existing `argparse` block in `main()`, parallel to `--claude-dir`, `--vscode-dir`,
`--copilot-cli-dir`.
