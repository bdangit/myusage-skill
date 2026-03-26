# myusage-skill Development Guidelines

Last updated: 2026-03-26

## What this repo is

A skill (runnable by any LLM agent — Claude Code, GitHub Copilot, or other) that generates a
self-contained HTML insights report from local AI tool chat history (Claude Code, Copilot VS Code, Copilot CLI, OpenAI Codex).

## Governing Principles

All development is governed by the project constitution at
[`.specify/memory/constitution.md`](.specify/memory/constitution.md) (v1.2.0).

The six non-negotiable principles are: **Evals-First**, **Agent CLI Agnostic**,
**Zero Dependencies**, **Simplicity**, **Trunk-Based Development**, and
**LLM-Agnostic Insights**. Read the constitution before making any design decisions.

## Active Technologies

- **Language**: Python 3.10+ (stdlib only — no pip installs; `sqlite3` module used for Codex support)
- **Frontend**: Chart.js 4.x (fetched from CDN at report generation time, inlined into output HTML)

## Project Structure

```text
myusage-skill/
├── SKILL.md                        # Skill definition (triggers + agent instructions)
├── AGENTS.md                       # This file (agent-agnostic guidelines)
├── CLAUDE.md                       # Claude Code-specific variant of this file
├── skills/myusage/scripts/
│   └── generate_report.py          # Report generator
└── evals/
    ├── evals.json                   # Eval definitions
    └── fixtures/                    # Synthetic test data mirroring real source layouts
        ├── claude_code/
        ├── copilot_vscode/
        ├── copilot_cli/
        └── codex/                   # Codex fixtures: state_5.sqlite + sessions/*.jsonl
```

## Commands

```bash
# Run the report generator
python skills/myusage/scripts/generate_report.py

# Run evals
python -m unittest discover -s evals -p "test_*.py"
```

## Code Style

- Python 3.10+ standard conventions
- No external linting tools required (stdlib only project)

## Feature Branches

- `001-usage-insights-report` — core report generation (complete, merged to main)
- `002-copilot-pru-cost` — PRU and token cost comparison spec (merged to main)
- `003-gha-cicd-pipeline` — GHA CI/CD pipeline with validate + release jobs (complete, merged to main)
- `004-codex-support` — OpenAI Codex CLI session parsing and report integration (spec in progress)

<!-- MANUAL ADDITIONS START -->

## Key Implementation Notes (004-codex-support)

- Codex sessions live in `~/.codex/state_5.sqlite` — use `sqlite3` (stdlib) to read
- Discover database by globbing `state_*.sqlite` and picking the highest version N
- Each thread row has a `rollout_path` column pointing to the JSONL rollout file
- Model is in `threads.model` (nullable); fall back to first `turn_context` event in JSONL
- Store combined token total in new `Session.total_tokens` field (`input_tokens=None`, `output_tokens=None`)
- Cost estimation is omitted for Codex (no input/output token split available)
- Tool identifier is `"codex"` regardless of session source (cli/vscode)
- Eval fixtures use a pre-built `state_5.sqlite` with placeholder rollout paths that tests rewrite to absolute paths at runtime

<!-- MANUAL ADDITIONS END -->
