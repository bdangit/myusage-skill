# myusage-skill Development Guidelines

Last updated: 2026-03-17

## What this repo is

A skill (runnable by any LLM agent — Claude Code, GitHub Copilot, or other) that generates a
self-contained HTML insights report from local AI tool chat history (Claude Code, Copilot VS Code, Copilot CLI).

## Governing Principles

All development is governed by the project constitution at
[`.specify/memory/constitution.md`](.specify/memory/constitution.md) (v1.2.0).

The six non-negotiable principles are: **Evals-First**, **Agent CLI Agnostic**,
**Zero Dependencies**, **Simplicity**, **Trunk-Based Development**, and
**LLM-Agnostic Insights**. Read the constitution before making any design decisions.

## Active Technologies

- **Language**: Python 3.8+ (stdlib only — no pip installs)
- **Frontend**: Chart.js 4.x (fetched from CDN at report generation time, inlined into output HTML)

## Project Structure

```text
myusage-skill/
├── SKILL.md                        # Skill definition (triggers + agent instructions)
├── AGENTS.md                       # This file (agent-agnostic guidelines)
├── CLAUDE.md                       # Claude Code-specific variant of this file
├── scripts/
│   └── generate_report.py          # Report generator
└── evals/
    ├── evals.json                   # Eval definitions
    └── fixtures/                    # Synthetic test data mirroring real source layouts
        ├── claude_code/
        ├── copilot_vscode/
        └── copilot_cli/
```

## Commands

```bash
# Run the report generator
python scripts/generate_report.py

# Run evals
python -m unittest discover -s evals -p "test_*.py"
```

## Code Style

- Python 3.8+ standard conventions
- No external linting tools required (stdlib only project)

## Feature Branches

- `001-usage-insights-report` — core report generation (complete, merged to main)
- `002-copilot-pru-cost` — PRU and token cost comparison spec (PR open, spec phase)

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
