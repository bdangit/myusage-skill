# CLI Contract

**Feature**: 001-usage-insights-report
**Scope**: Invocation interface for the skill and the underlying Python script

---

## 1. Skill Invocation

This is a SKILL.md-based skill. It is triggered by natural language; there is no command to
remember or type verbatim.

**Example trigger phrases**:

- "Generate my usage report"
- "Show me my AI usage insights"
- "Create an insights report from my chat history"
- "How am I using AI tools?"

When the agent recognises one of these (or equivalent) requests, it reads `SKILL.md`, then
executes the Python script as described below.

---

## 2. What the Skill Instructs the Agent to Do

The skill instructs the agent to:

1. Locate `scripts/generate_report.py` relative to the skill's own directory.
2. Run it with Python 3 using the arguments provided by the user (if any), or with defaults if
   the user provides no override arguments.
3. Relay the script's stdout output to the user, including the final path of the generated report.
4. If the script exits with a non-zero exit code, relay the error message and exit code to the
   user.

The agent does not parse or interpret the report — it generates and opens it.

---

## 3. Python Script CLI

**Script path** (relative to repo root): `scripts/generate_report.py`

**Invocation**:

```
python scripts/generate_report.py [OPTIONS]
```

**Options**:

| Flag | Type | Default | Description |
|---|---|---|---|
| `--output PATH` | string | `~/Desktop/myusage-report.html` | Path where the generated HTML report is written. The directory must already exist. |
| `--days N` | integer | (all history) | Limit history to the most recent N days. Sessions with a `start_time` older than N days before the current time are excluded. If omitted, all available history is included. |
| `--claude-dir PATH` | string | `~/.claude/projects/` | Override the directory scanned for Claude Code JSONL history files. |
| `--vscode-dir PATH` | string | `~/Library/Application Support/Code/User/workspaceStorage/` | Override the directory scanned for Copilot VS Code chat session files. |
| `--copilot-cli-dir PATH` | string | `~/.copilot/session-state/` | Override the directory scanned for Copilot CLI event JSONL files. |

All path arguments accept `~` expansion.

**Examples**:

```bash
# Generate report with defaults
python scripts/generate_report.py

# Limit to last 30 days
python scripts/generate_report.py --days 30

# Write report to a custom location
python scripts/generate_report.py --output ~/Documents/ai-report.html

# Use non-standard data directories (e.g., for testing)
python scripts/generate_report.py \
  --claude-dir /tmp/test-data/claude \
  --vscode-dir /tmp/test-data/vscode \
  --copilot-cli-dir /tmp/test-data/copilot-cli
```

---

## 4. Exit Codes

| Code | Meaning |
|---|---|
| `0` | Report generated successfully. The output path is printed to stdout. |
| `1` | No data found. None of the three source directories contained readable session data. A human-readable message is printed to stdout explaining which directories were checked. |
| `2` | Error reading or parsing source files, fetching Chart.js, or writing the output file. A human-readable error message and the failing file path (if applicable) are printed to stderr. |

---

## 5. Stdout / Stderr Contract

**Stdout** receives:

- Progress messages as each data source is scanned, e.g.:
  ```
  Scanning Claude Code history: ~/.claude/projects/ ... 42 sessions found
  Scanning Copilot VS Code history: ~/Library/Application Support/... ... 18 sessions found
  Scanning Copilot CLI history: ~/.copilot/session-state/ ... 7 sessions found
  Fetching Chart.js from CDN ...
  Generating report ...
  Report written to: ~/Desktop/myusage-report.html
  ```
- On exit code 1, a message such as:
  ```
  No chat history found. Checked:
    Claude Code:     ~/.claude/projects/
    Copilot VS Code: ~/Library/Application Support/Code/User/workspaceStorage/
    Copilot CLI:     ~/.copilot/session-state/
  ```

**Stderr** receives:

- Error messages on exit code 2, e.g.:
  ```
  Error: Failed to fetch Chart.js from https://cdn.jsdelivr.net/npm/chart.js
  HTTPError: 503 Service Unavailable
  ```
  or:
  ```
  Error: Failed to parse ~/.claude/projects/my-project/abc123.jsonl on line 47
  JSONDecodeError: Expecting value: line 1 column 1 (char 0)
  ```

Corrupted or unreadable individual files are skipped with a warning to stderr; the script
continues processing remaining files and exits 0 if at least one valid session is found.

---

## 6. Report Output Format

The output is a **single self-contained HTML file**.

- No external assets are loaded at view time. Chart.js is inlined in a `<script>` tag.
- No internet connection is required to view the report after it is generated.
- No local server is required. The file can be opened directly in any modern browser via
  `File > Open` or `open ~/Desktop/myusage-report.html` on macOS.
- The file is human-readable but not intended to be edited manually.

**Report sections** (in display order):

1. **Summary digest** — Headline stats and the single most interesting insight from each category.
2. **Tool usage split** — Session count and message volume per tool, cross-tool comparison chart.
3. **Usage patterns** — Hourly heatmap and day-of-week activity chart.
4. **Session depth** — Average and median session length; session depth distribution chart; flow
   state sessions highlighted.
5. **Conversation categories** — Category breakdown chart aggregated across all tools, and a
   per-tool category breakdown.
6. **Mode breakdown** — Agent vs. ask mode split per tool (omitted if no mode metadata is
   available).
7. **Model usage** — Model frequency chart and trend over time (omitted if no model metadata is
   available).
