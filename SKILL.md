---
name: myusage
description: >
  Generate a personal AI usage insights report from local chat history.
  Use this skill when the user asks about their AI usage, tool usage stats,
  how they use AI, usage insights report, usage patterns, chat history analysis,
  understanding their AI tool habits, how much they use Claude or Copilot,
  their most-used AI models, when they use AI most, agent vs ask mode breakdown,
  session character analysis, autonomous sessions, deeply engaged sessions,
  conversation categories, debugging vs code generation breakdown,
  or anything about understanding their AI tool habits and work patterns.
  Trigger eagerly — if the user mentions insights, stats, report, history,
  or patterns in the context of AI tools, invoke this skill.
---

You are helping the user generate a personal AI usage insights report.

If the user just wants a quick report without AI-generated narrative insights, skip Phase 2 and run the report script without `--insights`. Tell them they can ask for "insights" next time to get narrative observations.

---

## Phase 1 — Extract data

First, determine the time window from the user's request:
- Default (no qualifier): use `--days 180` (6 months)
- User says "all time", "full history", "everything": use `--days 0`
- User says "last 30 days", "this month", etc.: use the appropriate number (e.g. `--days 30`)

Run the following command and read its stdout carefully — it contains structured JSON about the user's conversation history:

```
python3 {SKILL_DIR}/scripts/generate_report.py --extract --days 180
```

The JSON includes: a summary (totals, peak hour, peak day, avg session duration, tools used, data window), session character breakdown (autonomous/deeply_engaged/general), conversation categories, top projects, models used, and all sessions in the data window (6 months by default) across ALL tools (Claude Code, VS Code, Copilot CLI), with up to 6 user messages each.

Read the data thoroughly before writing insights. The `conversations` array covers all tools — look at sessions from each tool to get a holistic view.

---

## Phase 2 — Generate insights

> **Note:** For best results, use a high-capability model (e.g. Claude Sonnet, GPT-4o). Lower-tier or free-tier models may produce generic or shallow insights.

Analyze the extracted data carefully — read the actual conversation messages, not just the summary stats.

Write insights as JSON to `/tmp/myusage-insights.json` in exactly this format:

```json
{
  "headline": "One or two sentences summarizing the most interesting or defining thing about how this person uses AI — personal, specific, grounded in what you actually read.",
  "work_themes": [
    {
      "name": "Infrastructure & DevOps",
      "description": "Setting up VMs, Docker, servers, and dev environments — 1-2 sentences on what specifically they do.",
      "session_count": 42
    },
    {
      "name": "Python Tooling",
      "description": "Writing CLI scripts, report generators, and data processing pipelines.",
      "session_count": 28
    }
  ],
  "at_a_glance": {
    "whats_working": "1-2 sentences on what's clearly going well in how they use these tools.",
    "whats_hindering": "1-2 honest sentences on patterns that slow them down or suggest underuse."
  },
  "sections": [
    {
      "title": "How You Use These Tools",
      "bullets": ["...", "...", "..."]
    },
    {
      "title": "How to Go More Autonomous",
      "bullets": [
        "**CLAUDE.md context**: Add a CLAUDE.md to your kbstudio repo... [learn more](https://docs.anthropic.com/en/docs/claude-code/memory). Example: `echo '## Context\\nThis repo tracks...' > CLAUDE.md`",
        "**Custom /commands**: Encode your VM setup as a slash command... [docs](https://docs.anthropic.com/en/docs/claude-code/slash-commands). Try: create `.claude/commands/start-momo.md`",
        "**PostToolUse hook**: Auto-commit after Claude writes files... [hooks docs](https://docs.anthropic.com/en/docs/claude-code/hooks)"
      ]
    }
  ]
}
```

What makes good insights:
- **For `work_themes`**: Return 3–5 themes named after what the work actually IS — concrete and specific (e.g. "Dotfiles & Shell Config", "Small Business Launch", "Python Tooling"). Analyze the `categories` stats and `conversations` messages. Avoid generic names like "Debugging" or "Code Generation". `session_count` is an approximate count from the conversations you observed.
- **Read the messages** — the actual conversation content is in `conversations[].messages`. Use it. Don't just summarize the stats.
- **Be specific** — name real project paths (`work/dotfiles`, `work/myusage-skill`), real topics from conversations, real tools they use
- **Be personal** — write in second person ("You tend to...", "Your sessions often...")
- **Be honest** — if most sessions are short bursts, say so; if they rarely go autonomous, say so
- **For sections** — write `"bullets"` (array of 3–5 strings) instead of `"body"` (paragraph). Each bullet is one punchy observation or recommendation.
- **For "How to Go More Autonomous"** — each bullet must:
  - Start with **Bold feature name**: then a description grounded in something you saw in their sessions
  - Include a markdown link to the official docs or product page (use real URLs listed below)
  - Include a short code snippet or config example where applicable (inline backtick or short fenced block)
  - Reference specific skills (e.g., `document-skills:skill-creator`), MCP servers, or config files by name
  - Look at what they repeatedly do manually and suggest the feature that automates it
- **Avoid generic statements** — never write "You use AI as a powerful tool" or "AI helps you be productive"

For product links, use these real URLs:
- Claude Code memory/CLAUDE.md: https://docs.anthropic.com/en/docs/claude-code/memory
- Custom slash commands: https://docs.anthropic.com/en/docs/claude-code/slash-commands
- Hooks: https://docs.anthropic.com/en/docs/claude-code/hooks
- MCP servers: https://docs.anthropic.com/en/docs/claude-code/mcp
- Settings/permissions: https://docs.anthropic.com/en/docs/claude-code/settings
- GitHub Copilot custom instructions: https://docs.github.com/en/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot

---

## Phase 3 — Generate report

Run (using the same `--days` value as Phase 1):

```
python3 {SKILL_DIR}/scripts/generate_report.py --days 180 --insights /tmp/myusage-insights.json --output ~/Desktop/myusage-report.html
```

Then open the report:

```
open ~/Desktop/myusage-report.html
```

Tell the user: "Your insights report is ready at ~/Desktop/myusage-report.html"
