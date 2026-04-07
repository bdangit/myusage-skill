# Quickstart: Codex Platform Support

This guide explains how Codex session data flows into the myusage-skill report generator after implementation is complete.

## User Perspective

A user who has used both Copilot and Codex wants to see their combined AI tool usage in one report.

**Before (without Codex support)**:
```
$ /myusage
Generated report.html
  • Copilot sessions: 12
  • Claude Code sessions: 8
  • Total tokens: 2.4M
  (no Codex data)
```

**After (with Codex support)**:
```
$ /myusage
Generated report.html
  • Copilot sessions: 12
  • Claude Code sessions: 8
  • Codex sessions: 5        ← NEW
  • Total tokens: 2.8M       ← Updated
  • Platform breakdown chart includes Codex series
  • Activity timeline shows Codex activity alongside other tools
```

## Developer Perspective

### Where Codex Data Lives

Codex stores session history locally:
```
~/.codex/
├── state_1.sqlite       (older version, skip)
├── state_5.sqlite       (current version, use this)
└── rollouts/
    ├── session-id-1.jsonl
    ├── session-id-2.jsonl
    └── ... (one file per session)
```

### Report Generator Workflow (Codex Module)

1. **Discovery**: Find the highest-versioned `state_N.sqlite` file in `~/.codex/`
2. **Open Database**: Connect to SQLite and query the `threads` table
3. **Extract Metadata**: For each thread, extract: id, created_at, updated_at, working_directory, tokens_used, cli_version, source, approval_mode
4. **Resolve Model Name**: 
   - If `model` field is not NULL, use it
   - If `model` is NULL, open the rollout JSONL file and search for the first `turn_context` event, extract model name
5. **Count User Messages**: Open the rollout JSONL file, count `response_item` events where `role == "user"`
6. **Categorize**: Apply existing keyword-based categorization (Debugging, Code Generation, Planning, etc.) to the first user message
7. **Classify Character**: Apply existing character classification (autonomous, deeply engaged, general) based on message count and session duration
8. **Merge into Report**: Add Codex sessions to the global sessions array and aggregate statistics

### Error Cases Handled

| Case | Behavior |
|------|----------|
| No Codex database found | Log info message, skip Codex, continue with report |
| Codex database corrupted | Log warning, skip Codex, continue with report |
| Codex database locked | Log warning, skip Codex, continue with report |
| Rollout file missing | Log warning, use database metadata only, continue |
| Rollout JSONL malformed | Log warning, skip detailed parsing, use database metadata only |

### Report Output Changes

**Platform Breakdown Chart**: Now includes Codex as a distinct series (same color scheme as other platforms)

**Activity Timeline**: Codex sessions appear on the same timeline as Copilot and Claude Code

**Session Categories**: Codex sessions grouped by category (Debugging, Code Generation, etc.)

**Character Distribution**: Codex sessions grouped by classification (autonomous, deeply engaged, general)

**Cost Columns**: Codex sessions display `—` (dash) with a footnote: "Cost estimates not available for Codex. The session database provides only combined token totals without input/output breakdown."

### Testing the Implementation

Synthetic fixtures are provided for eval purposes:

```
evals/fixtures/codex/
├── state_1.sqlite       (synthetic database with 3+ test sessions)
└── rollouts/
    └── session-*.jsonl  (synthetic rollout files)
```

Evals will:
- Verify Codex sessions are parsed correctly
- Verify model name resolution works (both from database and rollout files)
- Verify categorization and character classification are applied
- Verify cost columns show dashes
- Verify graceful skip when no Codex database is present
- Verify cross-platform aggregates include Codex data

## Integration Checklist (for Implementer)

- [ ] Add Codex database discovery logic to report generator
- [ ] Parse threads table and extract metadata
- [ ] Implement model name resolution (database → rollout file fallback)
- [ ] Implement user message counting from rollout JSONL
- [ ] Apply existing categorization logic to Codex sessions
- [ ] Apply existing character classification to Codex sessions
- [ ] Merge Codex sessions into global sessions array
- [ ] Update platform-level aggregates to include Codex
- [ ] Update all report charts to include Codex series
- [ ] Add cost column handling (dash for Codex) and footnote
- [ ] Create synthetic fixtures (state_1.sqlite + rollout JSONL files)
- [ ] Write evals for all user stories (EVAL-001 through EVAL-005)
- [ ] Test on Claude Code and at least one other agent CLI
- [ ] Verify evals pass
