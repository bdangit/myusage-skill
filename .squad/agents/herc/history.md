# Herc's Work Log

## Learnings

### Phase 1, Task T002 — Create Codex fixture directory structure

**Completed**: 2025-04-06

**Summary**:
- Directory structure created: `evals/fixtures/codex/`
- Subdirectories: `rollouts/`
- Placeholder: `state_1.sqlite` (empty file)
- Ready for Phase 3 fixture data (T010, T011)

**Structure**:
```
evals/fixtures/codex/
├── state_1.sqlite (empty placeholder)
└── rollouts/ (directory for JSONL rollout files)
```

**Next Steps**:
- Phase 2 tasks (T003-T009): Implement database discovery, session parsing, and model resolution
- Phase 3 tasks (T010-T011): Populate `state_1.sqlite` with synthetic Codex sessions and create JSONL rollout files

---

### Phase 3, Tasks T010 & T011 — Create Codex synthetic fixtures

**Completed**: 2025-04-06

**Summary**:
- Created `state_1.sqlite` with 3 synthetic Codex sessions
- Generated 3 rollout JSONL files (session-001.jsonl, session-002.jsonl, session-003.jsonl)
- Total: 3 sessions, 22 user messages across all sessions, 5200 total tokens

**Fixture Files Created**:
- `evals/fixtures/codex/state_1.sqlite` — SQLite database with threads table
- `evals/fixtures/codex/rollouts/session-001.jsonl` — 8 user messages, claude-opus-4.6
- `evals/fixtures/codex/rollouts/session-002.jsonl` — 10 user messages, model=NULL in DB (resolves from rollout)
- `evals/fixtures/codex/rollouts/session-003.jsonl` — 4 user messages, claude-haiku-4.5

**Session Details**:
1. **uuid-001**: 1500 tokens, claude-opus-4.6, CLI source, agentic mode
2. **uuid-002**: 2800 tokens, NULL model (tests resolution from rollout), VS Code source, on-request mode
3. **uuid-003**: 900 tokens, claude-haiku-4.5, CLI source, network-disabled mode

**Validation**:
- ✅ Database readable: `SELECT * FROM threads` returns 3 sessions
- ✅ JSONL files valid: Each file contains properly formatted JSON objects (one per line)
- ✅ Message counts verified: 8 + 10 + 4 = 22 user messages total
- ✅ Model resolution testable: Session 2 has model in turn_context event
- ✅ Schema correct: All required fields present with correct data types

**Ready For**:
- Phase 3 eval implementation (T012–T021): Codex discovery, parsing, aggregation, and integration tests
