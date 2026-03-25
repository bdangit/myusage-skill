# Implementation Plan: GHA CI/CD Pipeline

**Branch**: `003-gha-cicd-pipeline` | **Date**: 2026-03-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-gha-cicd-pipeline/spec.md`

## Summary

Add a single GitHub Actions workflow (`.github/workflows/ci.yml`) with two jobs — `validate` (runs on every PR and push to main) and `release` (runs on merge to main only after validate passes). Validation logic lives in `.github/scripts/validate.sh` (bash) for local reproducibility. The release job delegates the full release lifecycle to `googleapis/release-please-action@v4`, which reads conventional commits, opens a Release PR with the version bumped in `.claude-plugin/plugin.json`, and publishes a GitHub Release when the Release PR is merged. The `version` field is removed from `.claude-plugin/marketplace.json`.

## Technical Context

**Language/Version**: Bash (primary), Python 3.10 stdlib (version bump + JSON validation only)
**Primary Dependencies**: GHA actions only — `actions/checkout@v4`, `actions/setup-python@v5`, `googleapis/release-please-action@v4` (CI infrastructure, not runtime deps)
**Storage**: `.claude-plugin/plugin.json` (read/write), `.claude-plugin/marketplace.json` (read/validate)
**Testing**: Existing eval suite in `evals/` + new evals for validate.sh exit codes
**Target Platform**: `ubuntu-24.04` GHA runner + local macOS/Linux developer machines
**Project Type**: CI/CD pipeline (GHA workflow + shell scripts)
**Performance Goals**: validate job completes in < 60s; full pipeline (validate + release) in < 3 min
**Constraints**: Bash for scripts, Python stdlib only for any Python logic — no pip installs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Evals-First**: EVAL-001 through EVAL-007 defined in spec, covering all user stories.
- [x] **Agent Agnostic**: CI pipeline is infrastructure; no agent-specific syntax in design. validate.sh works from any terminal regardless of agent CLI.
- [x] **Zero Dependencies**: GHA actions are CI infrastructure (not runtime deps). Bash is built-in. Python stdlib only. No pip installs.
- [x] **Simplicity**: Single workflow file, one shell script, one Python inline script for version bumping. No abstractions beyond what's needed.
- [x] **Trunk-Based**: This is a spec branch — docs only. Implementation goes on `003-gha-cicd-pipeline-impl`.
- [x] **LLM-Agnostic Insights**: N/A — this feature is CI infrastructure, not skill output or report generation.

## Project Structure

### Documentation (this feature)

```text
specs/003-gha-cicd-pipeline/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── validate-sh.md
│   └── ci-workflow.md
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (repository root)

```text
.github/
├── workflows/
│   └── ci.yml                  # Single workflow: validate + release jobs
└── scripts/
    └── validate.sh             # Local-runnable validation script

release-please-config.json      # release-please: release type + extra-files for plugin.json
.release-please-manifest.json   # release-please: tracks current version

.claude-plugin/
├── plugin.json                 # Version source of truth (updated by release-please)
└── marketplace.json            # version field removed
```

**Structure Decision**: Flat — no src/ hierarchy needed. CI infrastructure lives entirely under `.github/`. No changes to `scripts/` (skill assets) or `evals/` (existing test suite).

## Complexity Tracking

No constitution violations. All gates pass.
