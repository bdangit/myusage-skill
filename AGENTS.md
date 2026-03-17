# myusage-skill Development Guidelines

Last updated: 2026-03-17

## What this repo is

A skill (runnable by any LLM agent — Claude Code, GitHub Copilot, or other) that generates a
self-contained HTML insights report from local AI tool chat history (Claude Code, Copilot VS Code, Copilot CLI).

## Design Principles

- **LLM-agnostic**: The skill and generated report must not assume a specific LLM or vendor. Avoid hardcoding "Claude", "Copilot", or any product name in user-facing text. The agent invoking the skill could be Claude, Copilot, or any future model.
- **Stdlib only**: No pip dependencies — keep the report generator runnable with bare Python 3.8+.
- **Self-contained output**: The generated HTML report must work with no external network requests after generation (Chart.js inlined at build time).

## Active Technologies

- **Language**: Python 3.8+ (stdlib only — no pip installs)
- **Frontend**: Chart.js 4.x (fetched from CDN at report generation time, inlined into output HTML)

## Project Structure

```text
myusage-skill/
├── SKILL.md                        # Skill definition (triggers + agent instructions)
├── CLAUDE.md                       # This file
├── scripts/
│   └── generate_report.py          # Report generator (to be implemented)
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

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
