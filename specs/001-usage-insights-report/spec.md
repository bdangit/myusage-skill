# Feature Specification: AI Usage Insights Report

**Feature Branch**: `001-usage-insights-report`
**Created**: 2026-03-14
**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Cross-Tool Usage Overview (Priority: P1)

As a developer who uses multiple AI agent CLIs daily, I want a single report showing how my
activity is distributed across Claude Code and GitHub Copilot — measured by session count and
message volume — so I can understand where I spend most of my AI-assisted work time.

**Why this priority**: Without knowing the tool split, no other insight has context. This is the
entry point of the report and the minimum viable output.

**Independent Test**: Point the skill at chat history from two tools and verify the report
produces a cross-tool usage breakdown with session counts and time percentages.

**Acceptance Scenarios**:

1. **Given** I have chat history from Claude Code and Copilot, **When** I run the skill, **Then**
   the report shows total sessions, total messages, and percentage of activity per tool in a
   comparison chart.
2. **Given** I only have history from one tool, **When** I run the skill, **Then** the report
   generates cleanly for the single tool without errors or empty sections.
3. **Given** I have no chat history files, **When** I run the skill, **Then** the report shows a
   clear, friendly message that no data was found rather than an error.

---

### User Story 2 — Usage Pattern Analysis (Priority: P2)

As a developer, I want to see when I use AI tools throughout the day and week — my busy hours,
active days, and overall rhythm — so I can understand my work patterns and identify my peak
productivity windows.

**Why this priority**: Temporal patterns are one of the highest-value insights; they reveal daily
habits and real focus windows in a way that raw counts don't.

**Independent Test**: Given timestamped history, the report shows an hourly heatmap and day-of-week
chart that accurately reflects the timing of sessions in the input data.

**Acceptance Scenarios**:

1. **Given** chat history with timestamps, **When** I view the report, **Then** I see an hourly
   heatmap showing my busiest hours across the week.
2. **Given** multi-week history, **When** I view the report, **Then** I see a day-of-week chart
   showing which days I use AI tools most.
3. **Given** history with a clear daily peak window, **When** I view the report, **Then** that
   peak window is visually highlighted or called out in the summary.

---

### User Story 3 — Conversation Depth & Flow State Detection (Priority: P2)

As a developer, I want to know how long and deep my AI conversations are, whether I'm in a flow
state during sessions, and how often I stay engaged versus drop in and out — so I can understand
the quality and depth of my AI-assisted work.

**Why this priority**: Depth and flow detection are what make this report feel like a genuine
personal insight tool rather than just a usage counter.

**Independent Test**: Given sessions with varying message counts and timing, the report correctly
identifies long vs. short sessions, flow vs. fragmented engagement, and average conversation depth.

**Acceptance Scenarios**:

1. **Given** my chat history, **When** I view the report, **Then** I see average and median
   conversation length by message count and by time, and a distribution chart of session depth.
2. **Given** sessions with 10+ messages sent rapidly over 15+ minutes, **When** I view the
   report, **Then** those sessions are flagged as likely flow state sessions.
3. **Given** sessions with large time gaps between messages, **When** I view the report, **Then**
   those sessions are identified as fragmented or interrupted rather than flow.

---

### User Story 4 — Mode & Model Breakdown (Priority: P3)

As a developer, I want to know what modes I use (agent/autonomous mode vs. ask/chat mode) and
which AI models I invoke — so I can understand whether I'm using AI as an executor or a
question-answering tool, and track my model preferences over time.

**Why this priority**: Mode and model data adds nuance but depends on the other stories giving
it meaningful context. Useful even when only one tool exposes this metadata.

**Independent Test**: Given history with mode and model metadata, the report shows per-tool
agent vs. ask mode percentages and a model frequency chart matching the input data.

**Acceptance Scenarios**:

1. **Given** history that includes mode metadata, **When** I view the report, **Then** I see a
   per-tool breakdown of agent mode vs. ask mode sessions as a percentage.
2. **Given** history that includes model names, **When** I view the report, **Then** I see a
   chart showing which models I use most and how that has shifted over time.
3. **Given** history with no mode or model metadata, **When** I view the report, **Then** those
   sections are omitted gracefully rather than showing empty or broken charts.

---

### User Story 5 — Chat & Message Categorization (Priority: P2)

As a developer, I want my conversations automatically grouped into general topic buckets — such as
debugging, code generation, learning/explanation, planning, writing, refactoring — so I can
understand what I actually use AI for and see how that breaks down across tools and over time.

**Why this priority**: Knowing *what* I use AI for is as valuable as knowing *when* — it surfaces
whether I'm using it as a coding tool, a thinking partner, a search engine, or something else.
This rounds out the picture of how I work with AI day-to-day.

**Independent Test**: Given a set of synthetic conversations with clearly typed content (e.g., one
debugging session, one code generation session), the report correctly assigns each to the expected
bucket and shows the distribution chart.

**Acceptance Scenarios**:

1. **Given** my chat history, **When** I view the report, **Then** I see a breakdown of my
   conversations by category (e.g., "Debugging 34%, Code Gen 28%, Learning 18%, Planning 12%,
   Other 8%") shown as a chart.
2. **Given** history from multiple tools, **When** I view the report, **Then** I see the category
   breakdown per tool, so I can see if I use Copilot differently than Claude Code.
3. **Given** a conversation that spans multiple topics, **When** I view the report, **Then** it
   is assigned to the single most dominant category rather than split across multiple.
4. **Given** a conversation that does not clearly fit any bucket, **When** I view the report,
   **Then** it appears in an "Other" catch-all category rather than being dropped.

---

### Edge Cases

- What happens when chat history files are partially corrupted or in an unexpected format?
- How does the skill handle very large history files spanning many months of data?
- What if two tools store timestamps in different timezone formats?
- What if a tool does not expose model name or mode in its history files?
- What if session start/end boundaries are ambiguous (e.g., no explicit session markers)?
- What if a conversation is genuinely multi-topic and no single category dominates?
- What if message content is very short (e.g., one-word replies) making categorization
  unreliable?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The skill MUST read chat history from all three sources without requiring the
  user to manually export or convert any data:
  - Claude Code: `~/.claude/projects/`
  - Copilot VS Code: `~/Library/Application Support/Code/User/workspaceStorage/`
  - Copilot CLI: `~/.copilot/session-state/`
- **FR-002**: The skill MUST produce a self-contained, single-file HTML report that opens in
  any modern browser without a server or internet connection.
- **FR-003**: The report MUST include visually rich charts for each insight category: tool usage
  split, hourly heatmap, session depth distribution, mode breakdown, model usage, and conversation
  category breakdown.
- **FR-004**: The skill MUST detect and visually highlight flow state sessions based on message
  density and session duration.
- **FR-005**: The report MUST include a headline summary section at the top with the single most
  interesting insight from each category — a personalized digest the user sees first.
- **FR-006**: The skill MUST show per-tool breakdowns for all metrics, not only aggregated totals.
- **FR-007**: The skill MUST operate with zero external runtime dependencies — all data parsing
  and report generation uses only standard library capabilities of the implementation language.
  Chart.js is the single approved client-side exception: it MUST be inlined into the HTML report
  at generation time so the report remains self-contained with no internet dependency at view time.
- **FR-008**: The skill MUST work identically when invoked from Claude Code and from GitHub
  Copilot agent CLI.
- **FR-009**: When metadata (mode, model name) is absent from history files, the report MUST
  omit those sections gracefully without showing errors or empty states.
- **FR-010**: The report MUST be visually high-quality — polished layout, readable typography,
  cohesive color scheme, and chart clarity appropriate for sharing with peers.
- **FR-011**: The skill MUST categorize each conversation into one of a fixed set of general
  topic buckets (Debugging, Code Generation, Learning/Explanation, Planning, Writing/Docs,
  Refactoring, Other) using keyword and pattern analysis of message content — no external AI
  call required.
- **FR-012**: The report MUST show the category breakdown as a chart, both aggregated across
  all tools and broken down per tool.
- **FR-013**: Every conversation MUST be assigned to exactly one category — the most dominant
  one. Conversations that don't fit a defined bucket go to "Other".

### Key Entities

- **Session**: A contiguous conversation in a single tool with start time, end time, message
  count, and optional metadata (mode, model name).
- **Message**: An individual user or assistant turn with timestamp and character count.
- **UsageSnapshot**: Aggregated metrics for a single tool across all its sessions.
- **InsightsReport**: The final artifact — a single self-contained HTML file combining all
  snapshots and visualizations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can generate a full insights report from local chat history in under
  30 seconds on a typical developer machine.
- **SC-002**: Spot-checking 5 random sessions against raw history files shows zero data
  discrepancies in the report's session counts and timing.
- **SC-003**: The report is fully readable and usable in any modern browser without plugins,
  internet access, or a local server.
- **SC-004**: A developer can identify their three busiest hours and their most-used model by
  reading the report in under 60 seconds.
- **SC-005**: The skill runs without modification on both Claude Code and GitHub Copilot agent
  environments, producing identical reports from the same input data.

### Eval Requirements *(mandatory — per constitution)*

Every user story MUST have at least one eval defined here before implementation begins.
Evals MUST be validated on Claude Code AND at least one other supported agent CLI.

- **EVAL-001 (US1)**: Given synthetic history files for two tools with known session counts,
  the generated report contains a cross-tool section with correct session counts and percentage
  split that matches the input data exactly.
- **EVAL-002 (US2)**: Given synthetic history with known timestamps, the hourly heatmap in the
  report correctly identifies the peak hour as the hour with the most messages in the input.
- **EVAL-003 (US3)**: Given a synthetic session with 12 messages over 22 minutes with all
  inter-message gaps under 3 minutes, the report correctly flags it as a flow state session.
- **EVAL-004 (US4)**: Given synthetic history with explicit model names and mode tags, the
  report correctly renders model and mode distributions that match the input data.
- **EVAL-005 (US5)**: Given synthetic conversations with clearly typed content — one session
  containing only debugging messages, one containing only code generation requests — the report
  assigns each to the correct bucket and the category chart reflects the expected distribution.

## Assumptions & Data Sources

### Claude Code

- **Location**: `~/.claude/projects/<project-dir>/<session-uuid>.jsonl`
- **Format**: JSONL — one JSON object per line
- **Relevant entry types**: `user` (user messages), `assistant` (model responses)
- **Key fields**:
  - `timestamp` (ISO 8601) — on every entry
  - `sessionId` — groups messages into a session
  - `message.content` — user message text (user entries)
  - `message.model` — model name e.g. `claude-opus-4-6` (assistant entries)
  - `message.usage.input_tokens` / `output_tokens` — token counts (assistant entries)
  - `cwd` — working directory at time of session
  - `version` — Claude Code version
- **Mode**: Claude Code is always agentic; no ask/agent split to detect.

### GitHub Copilot — VS Code Extension

- **Location**: `~/Library/Application Support/Code/User/workspaceStorage/<workspace-hash>/chatSessions/<session-uuid>.json`
- **Format**: JSON with a `requests` array
- **Key fields per request**:
  - `timestamp` (Unix ms) — message timestamp
  - `message.parts[].text` — user message text
  - `modelId` — model identifier
  - `timeSpentWaiting` — response latency ms
- **Key session-level fields**:
  - `sessionId`, `creationDate`, `lastMessageDate` (Unix ms)
  - `customTitle` — user-given session title if set
  - `inputState.mode.id` — `"agent"` or `"ask"` — the mode toggle
  - `inputState.selectedModel.metadata.id` — model name e.g. `claude-haiku-4.5`

### GitHub Copilot — CLI (`copilot` command)

- **Location**: `~/.copilot/session-state/<sessionId>/events.jsonl`
- **Format**: JSONL event log — one JSON event per line, linked via `parentId` chain
- **Key event types and fields**:
  - `session.start` — `sessionId`, `startTime` (ISO 8601), `selectedModel`, `copilotVersion`,
    `context.cwd`, `context.branch`, `context.repository`
  - `session.shutdown` — `sessionStartTime`, `totalApiDurationMs`, `currentModel`,
    `modelMetrics` (per-model token/cost breakdown)
  - `session.mode_changed` — `previousMode`, `newMode` — tracks agent/ask switches mid-session
  - `user.message` — `content` (message text), `agentMode` (boolean — true = agent mode)
  - `assistant.usage` — `model`, `inputTokens`, `outputTokens`, `cost`, `duration`
  - `assistant.message` — `content` (assistant response text)
- **Richer than VS Code**: exposes per-turn token counts, cost, latency, and per-message
  `agentMode` flag directly in the event stream

### Output

- Report written to `~/Desktop/myusage-report.html` as a single self-contained HTML file.

### General

- Flow state is defined as: a session with 10 or more messages where the median inter-message
  gap is under 5 minutes and total session duration exceeds 15 minutes.
- "Session duration" is derived from the timestamp of the first to last message in the session
  across all tools — none of the three sources expose a wall-clock active-time metric directly.
- The report is a point-in-time snapshot — no real-time updates needed.
- Chart rendering uses Chart.js inlined into the HTML output. The skill fetches Chart.js from
  its CDN at report generation time and embeds the full library source inline. No internet
  connection is required to view the report after it is generated.
- Chart.js is the single approved frontend exception to the zero-dependency rule.
- Implementation language: Python 3, stdlib only (no pip installs).
- Mode representation is normalized across tools: VS Code Copilot's `"agent"`/`"ask"` string
  and Copilot CLI's `agentMode` boolean are both mapped to a common `agent` / `ask` label in
  the report.

### Future Considerations

- **Cost / PRU tracking**: GitHub Copilot charges in Premium Request Units (PRU), not tokens.
  The Copilot CLI schema exposes `cost` and `quotaSnapshots` fields in `assistant.usage`, but
  real populated session data is needed to confirm whether PRU values are present and how to
  interpret them. Token counts from all sources are surfaced in v1. A cost/PRU section should
  be added in a future iteration once the data shape is validated against real sessions.
- **Additional tools**: Other agent CLIs (Gemini CLI, Cursor, etc.) could be added as data
  sources in future iterations using the same parser-per-tool pattern.
