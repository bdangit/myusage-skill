# Quickstart

**Feature**: 001-usage-insights-report

---

## What This Skill Does

The myusage-skill reads your local AI tool chat history from Claude Code, GitHub Copilot for VS
Code, and the GitHub Copilot CLI, then generates a single self-contained HTML report showing how
you use these tools. The report includes a cross-tool usage breakdown, an hourly activity heatmap,
session depth and flow state analysis, mode and model usage charts, and an automatic categorization
of your conversations by topic (debugging, code generation, learning, planning, writing, and
refactoring). The HTML file is written to your Desktop and opens in any browser with no internet
connection or local server required.

---

## Prerequisites

- **Python 3.8 or later** — the report generator uses the standard library only; no `pip install`
  is required.
- **Internet connection at generation time** — Chart.js is fetched from its CDN once and embedded
  in the report. After the report is generated you can view it offline.
- **macOS** — v1 data source paths are macOS-specific. The default paths for Copilot VS Code
  (`~/Library/Application Support/...`) and Copilot CLI (`~/.copilot/...`) are macOS locations.
  All default paths can be overridden via CLI flags for use on other platforms.

---

## How to Invoke

Say one of these (or anything equivalent) to the agent:

- "Generate my usage report"
- "Show me my AI usage insights"
- "Create an insights report from my chat history"
- "How am I using AI tools?"

The agent will run the script and tell you where the report was saved. You can add optional
constraints in your request:

- "Generate my usage report for the last 30 days"
- "Generate my AI usage report and save it to my Documents folder"

---

## What Gets Generated

The report is written to `~/Desktop/myusage-report.html` by default.

Open it in any modern browser. It contains the following sections:

1. **Summary digest** — Headline numbers and the most notable insight from each section at a
   glance.
2. **Tool usage split** — How your sessions and messages are distributed across Claude Code,
   Copilot VS Code, and Copilot CLI.
3. **Usage patterns** — Hourly heatmap showing your busiest hours of the day and a day-of-week
   chart showing your most active days.
4. **Session depth** — Average and median conversation length, a distribution chart of session
   sizes, and your flow state sessions called out visually. (Flow state = 10+ messages, median
   inter-message gap under 5 minutes, session over 15 minutes.)
5. **Conversation categories** — Your sessions bucketed by topic (Debugging, Code Generation,
   Learning/Explanation, Planning, Writing/Docs, Refactoring, Other), shown as a chart
   aggregated across all tools and broken down per tool.
6. **Mode breakdown** — Agent mode vs. ask mode per tool. Shown only when mode metadata is
   available.
7. **Model usage** — Which AI models you invoke most often. Shown only when model metadata is
   available.

---

## Troubleshooting

### No data found for a tool

The script prints which directories it scanned. If a tool shows 0 sessions:

- Confirm the tool has been used and its history files exist at the expected path (see "Data
  Source Locations" below).
- If the files are in a non-standard location, pass the appropriate override flag:
  `--claude-dir`, `--vscode-dir`, or `--copilot-cli-dir`.
- If you have never used that tool, the section for it is omitted from the report automatically.

### Chart.js fetch fails

The script will print an error to stderr and abort. To resolve:

- Check your internet connection and try again.
- If you are behind a proxy, ensure Python's `urllib.request` can reach `cdn.jsdelivr.net`. This
  typically means the `HTTPS_PROXY` or `ALL_PROXY` environment variable is set correctly.
- If the CDN is temporarily unavailable, wait a few minutes and retry.

### A history file is skipped with a warning

Corrupted or partially-written JSON/JSONL files produce a warning but do not abort the run.
The script continues processing remaining files. If a large portion of your history is skipped,
check the stderr output for the specific file paths and inspect them manually.

### The report generates but looks blank for a section

Sections that require metadata (mode, model name) not present in your history files are omitted
gracefully. This is expected behaviour, not an error.

---

## Data Source Locations

| Tool | Default path |
|---|---|
| Claude Code | `~/.claude/projects/<project-dir>/<session-uuid>.jsonl` |
| Copilot VS Code | `~/Library/Application Support/Code/User/workspaceStorage/<hash>/chatSessions/<uuid>.json` |
| Copilot CLI | `~/.copilot/session-state/<sessionId>/events.jsonl` |

Full details on file formats and field mappings are in
[spec.md](./spec.md#assumptions--data-sources).
