# myusage-skill

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

A Claude Code / Copilot skill that reads your local AI tool chat history and generates a
polished, self-contained HTML insights report.

## What it shows you

- **Tool usage split** — how your sessions and messages are distributed across Claude Code,
  Copilot VS Code, and Copilot CLI
- **Usage patterns** — hourly heatmap and day-of-week activity breakdown
- **Session depth** — average conversation length, flow state detection
- **Conversation categories** — automatic bucketing by topic (debugging, code gen, learning,
  planning, writing, refactoring)
- **Mode breakdown** — agent mode vs. ask mode per tool
- **Model usage** — which models you invoke most

## Data sources

| Tool | Location |
|---|---|
| Claude Code | `~/.claude/projects/` |
| Copilot VS Code | `~/Library/Application Support/Code/User/workspaceStorage/` |
| Copilot CLI | `~/.copilot/session-state/` |

## Installation

```sh
/plugin marketplace add bdangit/myusage-skill
```

## Usage

Once installed, say to your agent: *"Generate my AI usage report"* or *"Show me my AI usage insights"*

The skill is also invocable directly as `/myusage`.

The report is written to `~/Desktop/myusage-report.html`.

## Requirements

- Python 3.8+
- Internet connection at generation time (Chart.js is fetched once and embedded in the output)
- macOS (v1 — data source paths are macOS-specific)

## Status

Spec and implementation plan complete. See `specs/001-usage-insights-report/` for full design
documentation.

Upcoming work tracked in [`TODO.md`](./TODO.md).
