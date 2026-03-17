# Implementation Plan: Copilot PRU and Claude Token Cost Comparison

**Branch**: `002-copilot-pru-cost` | **Date**: 2026-03-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/002-copilot-pru-cost/spec.md`

## Summary

Extend `scripts/generate_report.py` to compute estimated cost and session statistics for all
three supported tool sources (Copilot VS Code, Copilot CLI, Claude Code) by:

1. Adding `effective_prus` and `estimated_cost_usd` fields to the existing `Session` dataclass.
2. Adding module-level PRU multiplier table and token price schedule (one location each).
3. Computing cost values post-parse by walking the already-parsed `Session` list.
4. Adding "Cost & Usage" and "Session Insights" sections to the HTML report output.

No new files, no new dependencies. All work is inside `scripts/generate_report.py` and the
existing eval fixtures.

## Technical Context

**Language/Version**: Python 3.8+ (stdlib only — per constitution Principle III)
**Primary Dependencies**: None (stdlib only). Chart.js inlined at report generation time (approved exception).
**Storage**: Local filesystem — reads existing Copilot/Claude Code session files already parsed by feature 001.
**Testing**: `python -m unittest discover -s evals -p "test_*.py"`
**Target Platform**: macOS/Linux developer machine (same as existing feature 001)
**Project Type**: CLI tool — single Python script producing a self-contained HTML file
**Performance Goals**: Report generation in under 10 seconds on typical developer session history (~1000 sessions). No network calls.
**Constraints**: No pip dependencies; no external calls; generated HTML must be self-contained.
**Scale/Scope**: Single developer's local session history; no multi-user concerns.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Evals-First**: 6 evals defined in spec (EVAL-001 through EVAL-006), one per acceptance scenario group.
- [x] **Agent Agnostic**: Implementation is in a Python script with no agent-specific syntax. No CLAUDE.md or Copilot-specific execution paths in generator code.
- [x] **Zero Dependencies**: No new runtime dependencies. PRU multiplier table and price schedule are inline dicts. Chart.js remains the only approved exception.
- [x] **Simplicity**: Two new dataclass fields + two module-level dicts + one post-parse compute pass + two new HTML sections. Minimum viable design.
- [x] **Trunk-Based**: This is a spec branch (docs only). Implementation will happen on `002-copilot-pru-cost-impl` after this spec merges to `main`.
- [x] **LLM-Agnostic Insights**: Cost section labels derive from `session.tool` values (`copilot_vscode`, `copilot_cli`, `claude_code`), not hardcoded. Multiplier/price tables are keyed by model name (a data value), not vendor strings.

## Project Structure

### Documentation (this feature)

```text
specs/002-copilot-pru-cost/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code

All changes are within the existing single-file architecture:

```text
scripts/
└── generate_report.py       # All changes here

evals/
├── fixtures/
│   ├── claude_code/         # Existing (already has input_tokens/output_tokens)
│   ├── copilot_vscode/      # Existing (no token data — confirmed)
│   └── copilot_cli/         # Existing (has token data + assistant.usage)
└── test_*.py                # New eval tests for cost and session stats
```

**Structure Decision**: Single-file project. No new modules or packages. The `Session`
dataclass is extended in-place. Cost computation is a post-parse pass in `build_report()`
or a new `compute_session_costs()` helper function called from `build_report()`.

## Design Decisions

### 1. How cost fields are stored

Add two optional fields to the existing `Session` dataclass:

```python
effective_prus: Optional[float] = None      # Copilot sessions only
estimated_cost_usd: Optional[float] = None  # All sessions (None = price unknown)
```

**Rationale**: The `Session` dataclass is already the canonical unit of data throughout the
report pipeline. Adding two fields keeps cost co-located with the session it describes and
avoids introducing a parallel data structure. Consistent with the Simplicity principle.

### 2. Where the price tables live

Two module-level dicts, defined once, near the top of the file after the dataclass block:

```python
# PRU multipliers — last verified 2026-03-17
# Source: https://docs.github.com/en/copilot/...
PRU_MULTIPLIERS: Dict[str, float] = {
    "gpt-4o": 1.0,
    "claude-haiku-4.5": 1.0,
    "claude-sonnet-4-6": 1.0,
    "claude-opus-4-6": 3.0,
    # add new models here
}
PRU_DEFAULT_MULTIPLIER = 1.0
PRU_UNIT_PRICE_USD = 0.04  # USD per PRU, list price

# Token prices (USD per million tokens) — last verified 2026-03-17
TOKEN_PRICES: Dict[str, Dict[str, float]] = {
    "claude-haiku-4.5": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-6":   {"input": 15.00, "output": 75.00},
    # add new models here
}
```

**Rationale**: One location per table — satisfies SC-006. A comment with the verified date
prompts manual updates when vendors reprice.

### 3. When cost is computed

A new `compute_session_costs(sessions: List[Session]) -> None` function mutates sessions
in-place after parsing, called once in `build_report()`. This separates parsing concerns
(what the files say) from cost logic (what it means in USD), keeping each function focused.

### 4. Per-request model tracking for Copilot VS Code

The existing `parse_copilot_vscode` reads each request's `modelId` but only stores the
first non-null value as `session.model`. For accurate PRU calculation, different models
within a session have different multipliers and should be counted separately.

**Decision**: Extend `parse_copilot_vscode` to also populate a new optional field
`model_request_counts: Optional[Dict[str, int]]` on `Session`. The cost computation step
uses this per-model count when present, falling back to `session.model × message_count`
when absent (covers CLI and Claude Code, which are single-model per session).

This is the minimum change needed to be accurate. For CLI and Claude, `model_request_counts`
is `None` and the fallback path runs.

## Complexity Tracking

No constitution violations. No unapproved abstractions.

---

## Resolved Design Issues

The following issues were identified during plan review and resolved before task generation.

### Issue 1 — CLI duration: use timestamp-based, ignore `totalApiDurationMs` ✅

**Resolution**: Use wall-clock timestamp derivation for all three sources (consistent).

`totalApiDurationMs` is cumulative API inference time — the total time the CLI spent
waiting for model responses, excluding user think time and gaps between turns. For example,
`session-cli-002` has a 6-minute wall-clock session but `totalApiDurationMs` = 5.5 minutes;
the gap is reading/typing time between turns. It is not comparable to the duration values
derived from timestamps for VS Code and Claude Code, so it is out of scope for this feature.

All three sources use: `duration_seconds = (end_time - start_time).total_seconds()`
The spec's Unified Session Model table will be updated to reflect this.

---

### Issue 2 — `interaction_count` maps to existing `message_count` ✅

**Resolution**: No new field. `interaction_count` in the spec = `message_count` in code.
The display label "Interactions" will be used in the report. The spec's Unified Session
Model table will be updated to show the mapping.

---

### Issue 3 — US3 adds cost figures to existing session stats layout ✅

**Resolution**: US3 is not a brand-new section. It extends the existing per-tool stats
layout in `render_html()` to include `estimated_cost_usd` and `effective_prus` alongside
the session counts and durations already rendered. Implementation scope is narrower than
the spec implies.

---

### Issue 4 — VS Code per-request model tracking via `model_request_counts` ✅

**Resolution**: Extend `parse_copilot_vscode` to populate an optional
`model_request_counts: Optional[Dict[str, int]]` field on `Session`. The cost computation
step uses this per-model count when present, falling back to `session.model × message_count`
otherwise (covering CLI and Claude Code, which are single-model per session).
