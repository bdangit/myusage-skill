<!-- Sync Impact Report
Version change: 1.1.0 → 1.2.0 (added Principle VI: LLM-Agnostic Insights)
Added sections: VI. LLM-Agnostic Insights
Modified principles: none
Removed sections: none
Templates updated:
  ✅ .specify/templates/plan-template.md — Constitution Check updated with LLM-Agnostic Insights gate
Deferred TODOs: none
-->

# myusage-skill Constitution

## Core Principles

### I. Evals-First (NON-NEGOTIABLE)

Every feature MUST include evals, and all evals MUST pass before a feature is considered complete.
Evals are not optional, not deferrable, and not waivable under any circumstance.

**Rationale**: A skill that cannot be verified is a skill that cannot be trusted. Shipping without
passing evals means shipping unknown behavior. This project exists to produce reliable, measurable
output — evals are the proof of that.

### II. Agent CLI Agnostic

The skill MUST work identically across all major agent CLIs, including at minimum Claude Code and
GitHub Copilot. No feature, instruction, or assumption may be specific to a single agent unless
an explicit fallback path exists for all other supported agents.

**Rationale**: Locking behavior to one CLI limits reach and creates invisible incompatibilities.
Instructions must use neutral language and avoid agent-specific syntax, tool names, or APIs.
When testing, evals MUST be validated against more than one agent.

### III. Zero Dependencies

> **Approved exception**: Chart.js may be used as an inlined client-side asset in HTML report
> output. It is not a runtime dependency of the skill itself — it is bundled into the generated
> artifact. All other runtime, build, and parsing dependencies remain stdlib-only.

The skill MUST use no external runtime dependencies unless no reasonable alternative exists.
If a dependency is unavoidable, it MUST be justified in the Complexity Tracking section of the
implementation plan, and the justification MUST explain why a stdlib or built-in approach was
insufficient.

**Rationale**: Dependencies add installation friction, version conflicts, and maintenance surface.
A skill is most portable and reliable when it relies only on what every environment already has.
Simple beats clever.

### IV. Simplicity

Solutions MUST be as simple as the problem allows. YAGNI (You Aren't Gonna Need It) applies to
all design decisions. Abstractions, helpers, and utilities are only justified when the same logic
appears in three or more places. Do not design for hypothetical future requirements.

**Rationale**: Over-engineering skills makes them harder to read, maintain, and debug. The right
amount of complexity is the minimum needed for the current task.

### V. Trunk-Based Development

All work flows through short-lived branches merged into `main`. No long-lived branches.
Each feature follows a strict two-phase branching model:

**Phase 1 — Spec branch** (`NNN-feature-name`):
Contains only spec and planning artifacts (spec.md, plan.md, research.md, data-model.md,
contracts/, quickstart.md, checklists/). No implementation code. Merged to `main` via PR
before any implementation begins.

**Phase 2 — Implementation branch** (`NNN-feature-name-impl`):
Branched from `main` after the spec branch is merged. Contains all implementation code,
tests, eval fixtures, and SKILL.md. Merged to `main` via PR after all evals pass.

**Rationale**: Keeping spec and implementation in separate PRs makes reviews focused and
legible. A spec PR is a design document review — reviewers can catch architectural issues
before a line of code is written. An implementation PR is a code review — reviewers can
focus on correctness without wading through spec markdown. It also ensures `main` always
has a complete spec before any implementation is attempted.

**Rules**:
- `/speckit.implement` MUST NOT be run on a spec branch. Always branch from `main` first.
- Spec branches MUST NOT contain `.py`, `.js`, or other implementation files.
- Implementation branches MUST have a merged spec branch in `main` before they are opened.
- All PRs target `main`. No PR-to-PR merges.

### VI. LLM-Agnostic Insights

The skill and all generated output MUST NOT assume, reference, or hardcode a specific LLM
vendor, model, or product name in any user-facing text, report content, labels, or chart
titles. Vendor names (e.g., "Claude", "Copilot", "GPT") MUST only appear as data values
derived from the user's own history files — never as baked-in assumptions.

The skill SHOULD aspire to gather insights from as many AI tool sources as possible.
New tool sources (chat history formats, CLI logs, IDE extensions) SHOULD be added
incrementally as they are identified. Each supported source MUST be independently parseable
and gracefully skipped when absent.

**Rationale**: This skill serves any developer using any AI tool. Hardcoding vendor names
creates implicit bias, reduces trust for non-Claude users, and requires code changes whenever
the AI tooling landscape shifts. Aspiring to broad tool coverage ensures the skill remains
useful as the ecosystem evolves.

**Rules**:

- Report labels, headings, and chart axes MUST use neutral terminology (e.g., "AI Tool",
  "Model", "Tool Source") rather than any specific product name.
- Vendor or model names appearing in the report MUST originate exclusively from parsed
  history data, not from hardcoded strings in the generator.
- Each data source parser MUST be independently testable and MUST NOT fail the report if
  its source directory is absent or empty.
- Adding a new tool source MUST include at least one eval fixture and one eval covering
  that source's parsing path.

## Quality Gates

Every feature branch MUST satisfy the following gates before merge:

- **Evals written**: At minimum one eval per user story.
- **Evals pass**: All evals pass with zero failures. No partial credit.
- **Agent parity**: Evals validated on Claude Code AND at least one other supported agent CLI.
- **Dependency audit**: Zero net-new runtime dependencies, or each is justified in plan.md.
- **Complexity audit**: No unapproved abstractions; any violation documented in Complexity Tracking.
- **LLM-agnostic audit**: No vendor names hardcoded in generator output; all report labels use
  neutral terminology.

## Governance

This constitution supersedes all other practices and preferences. Amendments require:

1. A written rationale for the change.
2. A version bump following semantic versioning:
   - MAJOR: principle removal or redefinition that breaks prior guarantees.
   - MINOR: new principle or section added.
   - PATCH: clarification, wording, or typo fix.
3. `LAST_AMENDED_DATE` updated to the amendment date.
4. Consistency propagation: all templates reviewed and updated to reflect the change.

All PRs must verify compliance with Quality Gates before merge.

**Version**: 1.2.0 | **Ratified**: 2026-03-14 | **Last Amended**: 2026-03-17
