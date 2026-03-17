# Feature Specification: Copilot PRU and Claude Token Cost Comparison

**Feature Branch**: `002-copilot-pru-cost`
**Created**: 2026-03-17
**Status**: Draft
**Input**: User description: "Extract cost, token, and session duration data from Copilot and
Claude local files; normalize into a comparable model for cross-tool insights reporting."

## Background

GitHub Copilot bills advanced interactions using **Premium Request Units (PRUs)**. A PRU
represents one premium AI interaction, with a model-dependent multiplier:

- Standard models (GPT-4o, etc.): 1× PRU per request
- Premium models (Claude Opus, etc.): 3× PRU per request

The list price is $0.04 USD per PRU beyond a plan's monthly allowance. The inputs to PRU
calculation — interaction count and model name — are stored in **local Copilot files**:

- **Copilot VS Code**: Session JSON files contain a `requests[]` array where every entry has a
  `modelId` field and a timestamp. The file-level `creationDate` and `lastMessageDate` fields
  (Unix ms) allow session duration to be derived.
- **Copilot CLI**: Session JSONL files contain `session.start` (ISO start time + model),
  `user.message` events (interaction count), `assistant.usage` per turn (token counts), and
  `session.shutdown` with `totalApiDurationMs` — duration is recorded directly.

Claude Code stores token counts and timestamps per turn in local JSONL files:

- **Claude Code**: Each assistant turn has `usage.input_tokens`, `usage.output_tokens`, model
  name, and a timestamp. Session duration is derived from the first `user` and last `assistant`
  timestamps within a session file.

No GitHub API or network calls are needed for any of this.

This feature extracts cost and session statistics from all three sources and normalizes them
into a **unified session model** so that cost, duration, and interaction depth can be compared
side-by-side across tools in the report.

## Unified Session Model

All three sources are normalized to a common shape before display. This is the canonical entity
that powers both cost and session stat views:

| Field | Copilot VS Code | Copilot CLI | Claude Code |
|---|---|---|---|
| `session_id` | `sessionId` | `sessionId` | `sessionId` |
| `tool_source` | `copilot_vscode` | `copilot_cli` | `claude_code` |
| `date` | `creationDate` (ms → date) | `session.start.startTime` | first user timestamp |
| `month` | derived | derived | derived |
| `model` | majority `modelId` in requests | `session.start.selectedModel` | majority model in turns |
| `duration_seconds` | `(lastMessageDate - creationDate) / 1000` | `(last_event_ts - start_ts)` | `(last_ts - first_ts)` |
| `interaction_count` | `len(requests)` = `message_count` | count of `user.message` = `message_count` | count of user turns = `message_count` |
| `input_tokens` | — (not recorded) | sum of `assistant.usage.inputTokens` | sum of `usage.input_tokens` |
| `output_tokens` | — (not recorded) | sum of `assistant.usage.outputTokens` | sum of `usage.output_tokens` |
| `effective_prus` | `interaction_count × multiplier` | `interaction_count × multiplier` | — |
| `estimated_cost_usd` | PRU-based | PRU-based | token-based |

Fields marked — are absent for that source and rendered as "N/A" in the report.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Extract and Normalize Copilot Sessions (Priority: P1)

A developer wants the skill to read all local Copilot VS Code and CLI session files, parse each
into a normalized Session record (with cost, duration, and interaction count), and make those
records available for the report — no network calls or auth required.

**Why this priority**: Copilot data extraction is the core new capability. The unified session
model must be established before comparison or display can happen.

**Independent Test**: Run the Copilot session extractor against the existing VS Code and CLI
fixture files; verify each returns correctly normalized Session records with accurate duration,
interaction count, effective PRUs, and estimated cost.

**Acceptance Scenarios**:

1. **Given** Copilot VS Code session files, **When** the skill runs, **Then** each file
   produces one Session record with: `duration_seconds` from `(lastMessageDate - creationDate)
   / 1000`, `interaction_count` from `len(requests)`, `model` from the majority `modelId`,
   `effective_prus` from `interaction_count × model_multiplier`, and `estimated_cost_usd`.
2. **Given** Copilot CLI session JSONL files, **When** the skill runs, **Then** each session
   produces one Session record with: `duration_seconds` from `totalApiDurationMs / 1000`,
   `interaction_count` from count of `user.message` events, `input_tokens` and `output_tokens`
   summed from `assistant.usage`, and `estimated_cost_usd` (PRU-based).
3. **Given** both VS Code and CLI Copilot data exist, **When** aggregated, **Then** Sessions
   from both sources appear in the same monthly view, each tagged with its `tool_source`.
4. **Given** a session uses a model not in the multiplier table, **When** parsed, **Then** a
   1× multiplier is assumed and the model is flagged "multiplier unknown."
5. **Given** no Copilot local files exist, **When** the skill runs, **Then** the Copilot
   section shows "No data" and report generation continues without error.

---

### User Story 2 - Extract and Normalize Claude Code Sessions (Priority: P2)

A developer wants the skill to read Claude Code JSONL session files, parse each into a
normalized Session record (with token-based cost, duration, and interaction count), and make
those records available for the report alongside Copilot sessions.

**Why this priority**: Claude Code data is already partially parsed by feature 001. This story
adds cost estimation and session normalization to what already exists.

**Independent Test**: Run the Claude Code session extractor against the existing eval fixtures;
verify each returns correctly normalized Session records with accurate duration (derived from
timestamps), interaction count, token totals, and estimated cost per model.

**Acceptance Scenarios**:

1. **Given** Claude Code JSONL files with `usage.input_tokens` and `usage.output_tokens`,
   **When** the skill runs, **Then** each session file produces one Session record with:
   `duration_seconds` from `(last_assistant_timestamp - first_user_timestamp)`,
   `interaction_count` from count of user turns, `input_tokens` and `output_tokens` summed,
   and `estimated_cost_usd` from the token price schedule.
2. **Given** a turn uses an unrecognized model name, **When** estimating cost, **Then** the
   turn appears with raw token counts but no USD estimate, labeled "price unknown."
3. **Given** no Claude Code history files exist, **When** the skill runs, **Then** the Claude
   section shows "No data" and report generation continues without error.

---

### User Story 3 - Cross-Tool Cost and Session Stats in Report (Priority: P3)

A developer opens the HTML report and sees a "Cost & Usage" section and a "Session Insights"
section. The cost section shows estimated USD spend per tool. The session section shows
comparable stats (duration, interaction count, session frequency) across all tools, making
it easy to understand both what AI tooling costs and how deeply it is being used.

**Why this priority**: The display layer depends on both extraction stories. It delivers the
user-visible value — one place to see AI spend and usage depth across tools.

**Independent Test**: Render the report against fixtures for all three sources; verify the HTML
contains cost figures, session stat figures, per-month breakdowns, source-tagged labels, and
graceful "N/A" placeholders when a field is absent for a source.

**Acceptance Scenarios**:

1. **Given** Sessions from all three sources, **When** the report renders, **Then** a "Cost &
   Usage" section shows each tool's estimated monthly spend and a combined total.
2. **Given** Sessions from all three sources, **When** the report renders, **Then** a "Session
   Insights" section shows per-tool: average session duration, average interactions per session,
   total sessions, and sessions per month.
3. **Given** only one tool's data is present, **When** the report renders, **Then** the missing
   tool shows "N/A" in both sections; the available tool's data renders normally.
4. **Given** cost data spanning multiple months, **When** displayed, **Then** a per-month
   breakdown is shown alongside the 6-month rollup for both cost and session stats.
5. **Given** a field is absent for a source (e.g., token counts for VS Code), **When**
   rendered, **Then** the cell shows "N/A" rather than zero or an error.
6. **Given** the report renders, **When** tool labels are inspected, **Then** no vendor names
   are hardcoded in the HTML template — all labels derive from parsed `tool_source` values.

---

### Edge Cases

- What if a Copilot VS Code session has `creationDate == lastMessageDate`?
  Duration is recorded as 0 seconds; the session is still included in counts.
- What if a Claude Code session file has only one turn (no duration span)?
  Duration is 0 seconds; all other fields still populate normally.
- What if a Copilot session spans midnight (crosses a month boundary)?
  Session is attributed to the month of its start time.
- What if a Claude Code session file has no `usage` fields on some turns?
  Those turns contribute to interaction count but not to token totals; remaining turns still
  sum correctly.
- What if a model name changes mid-session (Copilot VS Code allows per-request model)?
  The session's `model` field is set to the most-frequent model; the minority model's requests
  are still counted toward that session's PRU total using their own multiplier.
- What if a Copilot CLI session has no `session.shutdown` event (abrupt exit)?
  Duration falls back to `(last_event_timestamp - session.start.startTime)`; marked as
  "estimated" in the report tooltip.
- What if the user's Copilot plan covers all PRUs in the monthly allowance?
  Report shows PRU count and estimated cost at list price with a note that plan allowances
  may offset actual billed cost.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The skill MUST parse each Copilot VS Code session JSON file into a normalized
  Session record with `duration_seconds`, `interaction_count`, `model`, `effective_prus`, and
  `estimated_cost_usd`.
- **FR-002**: The skill MUST parse each Copilot CLI session JSONL file into a normalized
  Session record with `duration_seconds` (from `totalApiDurationMs` or timestamp fallback),
  `interaction_count`, `input_tokens`, `output_tokens`, `effective_prus`, and
  `estimated_cost_usd`.
- **FR-003**: The skill MUST parse each Claude Code session JSONL file into a normalized
  Session record with `duration_seconds` (derived from timestamps), `interaction_count`,
  `input_tokens`, `output_tokens`, and `estimated_cost_usd`.
- **FR-004**: The skill MUST apply a per-model PRU multiplier to Copilot interaction counts to
  compute `effective_prus`, defaulting to 1× for unrecognized models.
- **FR-005**: The skill MUST apply a per-model token price schedule to Claude token counts to
  compute `estimated_cost_usd`, marking unrecognized models as "price unknown."
- **FR-006**: The PRU multiplier table and the token price schedule MUST each be stored in a
  single, easily-editable location in the generator source code, with a "last verified" date
  comment.
- **FR-007**: The report MUST display a "Cost & Usage" section showing per-tool estimated
  monthly spend and a 6-month total, with all figures labeled "estimated."
- **FR-008**: The report MUST display a "Session Insights" section showing per-tool: total
  sessions, average session duration, and average interactions per session.
- **FR-009**: Both sections MUST include a per-month breakdown over the trailing 6-month window.
- **FR-010**: Fields absent for a given source (e.g., token counts for Copilot VS Code) MUST
  render as "N/A," not zero or an error.
- **FR-011**: All tool and model labels in the report MUST derive from parsed `tool_source`
  values, not from hardcoded vendor strings in the HTML template (per constitution Principle VI).
- **FR-012**: Missing or empty data sources MUST be handled gracefully — the report MUST
  generate successfully when one or more tool sources have no data.

### Key Entities

- **Session**: Normalized record per session across all sources (see Unified Session Model table
  above).
- **PRU Multiplier Table**: Model → multiplier lookup, with a 1× default for unknown models.
- **Token Price Schedule**: Model → {input_price_per_m, output_price_per_m} lookup.
- **Monthly Cost Summary**: Per-tool per-month rollup of `estimated_cost_usd` from all Sessions.
- **Monthly Session Summary**: Per-tool per-month rollup of `total_sessions`,
  `avg_duration_seconds`, `avg_interaction_count`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can see estimated USD spend per AI tool with no authentication and no
  network calls beyond running the skill.
- **SC-002**: Users can compare average session duration and interaction depth across tools in
  a single report view.
- **SC-003**: The report renders correctly when only one tool's data is present, with zero
  generation errors.
- **SC-004**: PRU totals derived by the skill match manually counted interaction totals for
  the eval fixtures within ±5%.
- **SC-005**: Claude token cost estimates are within ±10% of manually calculated amounts for
  the eval fixtures using published model pricing.
- **SC-006**: Adding a new model to either the PRU multiplier table or the token price schedule
  requires editing exactly one location in the source code.
- **SC-007**: All "N/A" placeholders for absent fields render correctly — no blank cells, no
  zeros standing in for missing data.

### Eval Requirements *(mandatory — per constitution)*

Every user story MUST have at least one eval before implementation begins. Evals MUST be
validated on Claude Code AND at least one other supported agent CLI.

- **EVAL-001 (US1-vscode)**: Given `copilot_vscode/workspace-abc123/chatSessions/session-vscode-001.json`,
  the VS Code extractor returns a Session with correct `duration_seconds`
  (`(lastMessageDate - creationDate) / 1000`), `interaction_count` (5), `model`
  (`claude-haiku-4.5`), and `estimated_cost_usd`.
- **EVAL-002 (US1-cli)**: Given `copilot_cli/session-cli-001/events.jsonl` and
  `session-cli-002/events.jsonl`, the CLI extractor returns one Session per file with correct
  `duration_seconds` from `totalApiDurationMs`, `interaction_count`, summed `input_tokens` and
  `output_tokens`, and `estimated_cost_usd`.
- **EVAL-003 (US1-missing)**: Given no Copilot local files, the skill generates the report
  successfully with the Copilot sections showing "No data."
- **EVAL-004 (US2)**: Given the existing Claude Code eval fixtures, the Claude extractor
  returns Session records with correct `duration_seconds` (timestamp-derived),
  `interaction_count`, `input_tokens`, `output_tokens`, and `estimated_cost_usd` per model.
- **EVAL-005 (US3-full)**: Given Sessions from all three sources (using existing fixtures),
  the generated report HTML contains a "Cost & Usage" section and a "Session Insights" section,
  each with correct per-tool monthly breakdowns, "estimated" labels on cost figures, "N/A"
  for absent token fields on VS Code sessions, and no hardcoded vendor names in the template.
- **EVAL-006 (US3-partial)**: Given Sessions from only one source, the report renders with
  "N/A" for the missing tools and no generation errors.

## Assumptions

- PRU estimation is derived locally from interaction counts and a stored multiplier table —
  no GitHub API or network calls are made.
- The PRU list price ($0.04/request) is applied to the full effective PRU count. A report note
  states that plan allowances may offset actual billed cost.
- Copilot CLI `assistant.usage.cost` fields are available as a secondary reference but are not
  used as the canonical cost figure — interaction-count derivation keeps VS Code and CLI
  consistent with each other.
- Claude Code session duration is an approximation (last assistant timestamp − first user
  timestamp). It does not capture idle time between turns or time after the last assistant
  response.
- All three sources derive `duration_seconds` from timestamps (wall-clock span from session
  start to last event). Copilot CLI records a `totalApiDurationMs` field (cumulative API
  inference time, excluding user think time) but this is a different quantity and is not used
  for session duration.
- Price schedules and PRU multiplier tables are updated manually; the last-verified date is
  recorded as a code comment.
- Claude Code token data already exists in the JSONL fixture files from feature 001. No new
  file format support is needed.
