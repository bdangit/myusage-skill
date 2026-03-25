# Feature Specification: Codex Platform Support

**Feature Branch**: `004-codex-support`  
**Created**: 2026-03-25  
**Status**: Draft  
**Input**: User description: "Build support for Codex. I want to pull AI insights from that platform."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Codex Sessions in Usage Report (Priority: P1)

A user who has been using the OpenAI Codex CLI or Codex in VS Code wants to run the myusage skill and see their Codex activity included in the generated report alongside Claude Code and Copilot sessions. Without any extra configuration, Codex sessions automatically appear in the insights — session count, total tokens consumed, models used, working directories, and session timeline.

**Why this priority**: This is the core deliverable. All other stories are enhancements on top of this foundational data ingestion. Without this, no Codex insights exist.

**Independent Test**: Can be fully tested by running the report generator against a fixture containing Codex session data and verifying the output HTML contains a Codex section with correct session count and token totals.

**Acceptance Scenarios**:

1. **Given** a user has Codex session data on their machine, **When** they invoke the myusage skill, **Then** the generated report includes a Codex section showing total sessions, total tokens used, date range of activity, and models used.
2. **Given** a user has zero Codex sessions, **When** they invoke the myusage skill, **Then** the Codex section is gracefully omitted from the report with no errors.
3. **Given** a Codex session database that is corrupted or locked, **When** the report generator encounters it, **Then** it logs a warning, skips Codex data, and continues generating the report for other platforms.

---

### User Story 2 - Codex Session Detail & Categorization (Priority: P2)

A user wants to understand not just that they used Codex, but *how* they used it — what kinds of tasks they worked on, how long sessions lasted, which projects they were in, and what collaboration mode was active (default agentic, network-disabled, etc.).

**Why this priority**: Without categorization and per-session detail, the report is just a raw count. Categorized insights are what make the report useful for understanding work patterns.

**Independent Test**: Can be tested by verifying that sessions parsed from a synthetic Codex fixture are assigned to meaningful categories (Debugging, Code Generation, etc.) using the same keyword-matching logic applied to other platforms.

**Acceptance Scenarios**:

1. **Given** Codex sessions with varied first user messages, **When** the report is generated, **Then** each session is assigned to a category (Debugging, Code Generation, Planning, etc.) consistent with how Claude Code and Copilot sessions are categorized.
2. **Given** a Codex session where the working directory maps to a known project, **When** viewing the report, **Then** the project path is shown for that session.
3. **Given** Codex sessions of varying length and interaction patterns, **When** the report is generated, **Then** each session is classified as autonomous, deeply engaged, or general using the same criteria applied to other platforms.

---

### User Story 3 - Codex Data in Cross-Platform Comparisons (Priority: P3)

A user wants to compare their Codex usage against their Claude Code and Copilot usage in aggregate charts — such as sessions per platform, tokens per platform, and activity over time across all tools.

**Why this priority**: Cross-platform comparison is the highest-level insight the report provides. This story depends on US1 and US2 being complete.

**Independent Test**: Can be tested by running the report against fixtures that include all three existing platforms plus Codex, and verifying the platform breakdown chart includes Codex as a distinct entry.

**Acceptance Scenarios**:

1. **Given** a user with sessions from Claude Code, Copilot CLI, Copilot VS Code, and Codex, **When** the report is generated, **Then** the platform breakdown chart includes Codex as a distinct series alongside the others.
2. **Given** Codex sessions spread over multiple days, **When** viewing the activity timeline, **Then** Codex activity appears in the correct date slots on the same timeline as other tools.

---

### Edge Cases

- What happens when the Codex session database exists but contains zero threads?
- What happens when a Codex session's rollout JSONL file is missing or deleted but the thread record still exists in the database?
- What happens when a thread's `model` field is NULL (default model was used) — is the correct model name still recovered?
- How does the system handle sessions launched from VS Code (`source: "vscode"`) vs. the terminal (`source: "cli"`) — are they parsed the same way?
- What happens when the Codex database schema version changes (e.g., `state_5.sqlite` becomes `state_6.sqlite`)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST discover Codex sessions from the Codex local session database (`~/.codex/state_N.sqlite`, where N is the highest available version number).
- **FR-002**: System MUST extract the following fields per session: session ID, start timestamp, end timestamp, working directory, total tokens used, CLI version, source (cli or vscode), and approval mode.
- **FR-003**: System MUST resolve the active model name for each session by reading the associated rollout JSONL file when the model is not present in the database record.
- **FR-004**: System MUST count user-initiated messages per session by reading the rollout JSONL file and counting `response_item` events with role `user` that contain non-system text.
- **FR-005**: System MUST apply the existing session character classification (autonomous, deeply engaged, general) to Codex sessions using the same criteria as other platforms.
- **FR-006**: System MUST apply the existing keyword-based session categorization (Debugging, Code Generation, Planning, etc.) to Codex sessions using the first user message and session content.
- **FR-007**: System MUST include Codex sessions in all aggregate report sections (platform breakdown, activity timeline, session character distribution, category distribution) alongside other platforms.
- **FR-008**: System MUST represent all Codex sessions under a single tool identifier `"codex"` in the data model and in the report, regardless of whether the session originated from the Codex CLI or VS Code extension. The `source` field (cli/vscode) MUST be stored per-session as metadata and displayed in per-session detail views, but MUST NOT split Codex into separate platform-level chart series.
- **FR-009**: System MUST gracefully handle a missing or inaccessible Codex session database by skipping Codex ingestion and continuing report generation.
- **FR-010**: System MUST include synthetic Codex fixture data (at least 3 sessions) in the eval fixtures directory, mirroring the structure of real Codex session files.
- **FR-011**: System MUST include at least one eval per user story that covers Codex parsing with the synthetic fixtures.
- **FR-012**: System MUST omit cost estimates for Codex sessions. The Codex session database provides only a combined `tokens_used` total without an input/output token split, making accurate pricing impossible. Cost columns for Codex MUST display a dash (`—`) and the report MUST include a footnote explaining this limitation.

### Key Entities

- **Codex Session**: A single Codex work session identified by a UUID. Has a start time, end time (derived from `updated_at`), working directory, total tokens consumed, model used, source (cli or vscode), approval mode, and first user message used as a title.
- **Codex Rollout File**: A JSONL event log for a session, located at the path recorded in the session database. Contains ordered events including `session_meta`, `turn_context` (with model name), `response_item` (user and assistant messages), and `event_msg` (task lifecycle).
- **Codex Session Database**: A SQLite file at `~/.codex/state_N.sqlite` (N = version number). The `threads` table is the primary source for session summaries. The highest-versioned file present is used.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All Codex sessions present in the local database are represented in the generated report — 0% sessions dropped during parsing when data is well-formed.
- **SC-002**: Session categories assigned to Codex sessions are consistent with those assigned to Claude Code and Copilot sessions for equivalent message content — category agreement rate ≥95% on shared test inputs.
- **SC-003**: The report generates successfully in the presence of Codex data within the same wall-clock time budget as reports without Codex (no measurable regression for typical session volumes under 500 sessions).
- **SC-004**: Users with no prior Codex usage see no errors, no empty sections, and no degraded report quality compared to a report generated before this feature existed.
- **SC-005**: All 3 user stories pass their respective evals on both Claude Code and Copilot CLI as required by the project constitution.

### Eval Requirements *(mandatory — per constitution)*

Every user story MUST have at least one eval defined here before implementation begins.
Evals MUST be validated on Claude Code AND at least one other supported agent CLI.

- **EVAL-001 (US1)**: Given the Codex eval fixtures (3+ synthetic sessions with known token counts and models), run the report generator and verify: (a) the report contains a Codex platform entry, (b) session count matches fixture count, (c) token totals match fixture data, (d) model names are correctly resolved from rollout files.
- **EVAL-002 (US1)**: Given no Codex database present, run the report generator and verify it completes without error and produces a valid report for other platforms.
- **EVAL-003 (US2)**: Given Codex fixture sessions with first user messages covering at least 3 different category keywords, verify each session is assigned the expected category.
- **EVAL-004 (US2)**: Given a fixture session with a NULL model in the thread record but a valid `turn_context` event in its rollout file, verify the correct model name appears in the report.
- **EVAL-005 (US3)**: Given fixtures for all 4 platforms (claude_code, copilot_cli, copilot_vscode, codex), run the report generator and verify the platform breakdown section includes a distinct Codex entry with correct aggregate values.
