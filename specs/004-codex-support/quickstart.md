# Quickstart: Codex Platform Support

## For users — see your Codex activity in the report

If you use the [OpenAI Codex CLI](https://github.com/openai/codex), your session data is
automatically included the next time you run the myusage skill. No configuration needed.

The skill reads from `~/.codex/state_5.sqlite` by default. If Codex is not installed or you
have no sessions, the Codex section is silently omitted — no errors, no degraded report.

---

## For contributors — running evals locally

```bash
# From repo root — runs all evals including the new Codex tests
python -m unittest discover -s evals -p "test_*.py"
```

Or run only the Codex evals:

```bash
python -m unittest evals.test_codex
```

---

## For contributors — understanding the Codex fixture

The synthetic fixtures live in `evals/fixtures/codex/`:

```text
evals/fixtures/codex/
├── state_5.sqlite               # Pre-built SQLite DB with 3 thread rows
└── sessions/
    ├── rollout-sess-001.jsonl   # Debugging session (tokens=1500, model="codex-mini-latest")
    ├── rollout-sess-002.jsonl   # Code Generation session (tokens=3200, model="o3")
    └── rollout-sess-003.jsonl   # NULL model session — model resolved from turn_context
```

The test setup copies `state_5.sqlite` to a temp directory and rewrites the `rollout_path`
values to point to the absolute paths of the JSONL files before running the parser. This
ensures the fixture works from any checkout location.

---

## For contributors — how Codex tokens appear in the report

Codex sessions include a **total token count** but no input/output split. In the report:

- The platform breakdown table shows "Tokens (total)" for Codex
- Cost columns display `—` for all Codex sessions
- A footnote explains why cost estimates are unavailable for Codex

This is consistent with FR-012 in the spec.

---

## For contributors — adding a new Codex session fixture

1. Create a new JSONL file in `evals/fixtures/codex/sessions/`
2. Add a corresponding row to `state_5.sqlite` using Python:

```python
import sqlite3, os

db_path = "evals/fixtures/codex/state_5.sqlite"
rollout_placeholder = "__FIXTURE_DIR__/sessions/rollout-sess-NEW.jsonl"

with sqlite3.connect(db_path) as conn:
    conn.execute("""
        INSERT INTO threads (id, rollout_path, created_at, updated_at, source,
                             model_provider, cwd, title, sandbox_policy,
                             approval_mode, tokens_used, has_user_event,
                             archived, cli_version, first_user_message, model)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?, ?)
    """, ("new-uuid", rollout_placeholder, <created_ts>, <updated_ts>,
          "cli", "openai", "/home/user/project", "Session title",
          '{"type":"read-only"}', "on-request", <tokens_used>,
          "1.2.3", "First user message", "codex-mini-latest"))
```

The `__FIXTURE_DIR__` placeholder is rewritten to the actual fixture directory path during test setup.
