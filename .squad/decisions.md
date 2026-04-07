# Squad Decisions

## Active Decisions

### Phase 1-2: Codex MVP Architecture ✅ (Complete)
**Status:** Approved, Implementation Complete
**Decision:** Unified "codex" platform (vs. split by source), single implementation file, stdlib-only
**Rationale:** Simplicity principle; source metadata stored per-session for detail views but not aggregated in charts
**Verification:** All 6 constitutional principles verified ✅ (Evals-First, Agent Agnostic, Zero Dependencies, Simplicity, Trunk-Based, LLM-Agnostic)

### Phase 2 Code Quality ✅ (Complete)
**Status:** Approved
**Decision:** Graceful degradation on missing/corrupted Codex DB (log warning, continue report generation)
**Rationale:** Robustness; users without Codex can still generate reports for Claude Code / Copilot platforms
**Implementation:** discover_codex_database() returns None if not found; parse_codex_database() returns [] on schema mismatch
**Verification:** Code compiles, fixtures tested, integration wired into main() pipeline

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
