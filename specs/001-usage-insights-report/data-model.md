# Internal Data Model

**Feature**: 001-usage-insights-report
**Status**: Decided

All types are Python dataclasses unless noted otherwise. No implementation code is shown here —
this document describes field names, types, and semantics only.

---

## Core Types

### `Message`

Represents a single turn in a conversation.

| Field | Type | Description |
|---|---|---|
| `timestamp` | `datetime` (UTC-aware) | When this message was sent or received |
| `role` | `str` | `"user"` or `"assistant"` |
| `content` | `str` | Raw text of the message |
| `char_count` | `int` | Derived: `len(content)` |

---

### `Session`

Represents a single conversation with one AI tool.

| Field | Type | Description |
|---|---|---|
| `session_id` | `str` | Unique identifier for this session, sourced from the underlying data |
| `tool` | `str` | `"claude_code"`, `"copilot_vscode"`, or `"copilot_cli"` |
| `project_path` | `Optional[str]` | Working directory or workspace path at the time of the session. Present for Claude Code (`cwd`) and Copilot CLI (`context.cwd`). Not available for Copilot VS Code. |
| `start_time` | `datetime` (UTC-aware) | Timestamp of the first message in the session |
| `end_time` | `datetime` (UTC-aware) | Timestamp of the last message in the session |
| `duration_seconds` | `float` | Derived: `(end_time - start_time).total_seconds()` |
| `messages` | `List[Message]` | All messages in the session (both user and assistant roles), in chronological order |
| `message_count` | `int` | Derived: count of `Message` entries where `role == "user"` |
| `model` | `Optional[str]` | Model name string as it appears in the source data (e.g., `"claude-opus-4-6"`, `"claude-haiku-4.5"`). `None` if not available. |
| `mode` | `Optional[str]` | Normalised mode label: `"agent"`, `"ask"`, or `None` if the source does not expose mode. Claude Code is always agentic but this field is left `None` rather than hardcoded, since Claude Code makes no agent/ask distinction in its data. |
| `input_tokens` | `Optional[int]` | Total input tokens across the session. Available from Claude Code (`message.usage.input_tokens` on assistant entries) and Copilot CLI (`assistant.usage.inputTokens`). Not available from Copilot VS Code. |
| `output_tokens` | `Optional[int]` | Total output tokens across the session. Same availability as `input_tokens`. |
| `category` | `str` | Category assigned by the categorizer. One of: `"Debugging"`, `"Code Generation"`, `"Learning/Explanation"`, `"Planning"`, `"Writing/Docs"`, `"Refactoring"`, `"Other"`. Always set. |
| `is_flow_state` | `bool` | Derived: `True` when `message_count >= 10` AND `median(inter_message_gaps) < 300` (seconds) AND `duration_seconds > 900`. All three conditions must hold. |
| `inter_message_gaps` | `List[float]` | Derived: list of elapsed seconds between consecutive user messages, in chronological order. Empty if `message_count < 2`. |

---

### `ToolSnapshot`

Aggregated metrics for a single AI tool across all of its sessions.

| Field | Type | Description |
|---|---|---|
| `tool` | `str` | Tool identifier: `"claude_code"`, `"copilot_vscode"`, or `"copilot_cli"` |
| `sessions` | `List[Session]` | All sessions parsed from this tool's data |
| `total_sessions` | `int` | Derived: `len(sessions)` |
| `total_messages` | `int` | Derived: sum of `session.message_count` (user messages only) across all sessions |
| `total_input_tokens` | `Optional[int]` | Derived: sum of `session.input_tokens` for sessions where it is not `None`. `None` if no session in this snapshot has token data. |
| `total_output_tokens` | `Optional[int]` | Derived: sum of `session.output_tokens` for sessions where it is not `None`. `None` if no session in this snapshot has token data. |
| `date_range_start` | `datetime` (UTC-aware) | Earliest `start_time` across all sessions in this snapshot |
| `date_range_end` | `datetime` (UTC-aware) | Latest `end_time` across all sessions in this snapshot |

---

### `InsightsReport`

The top-level aggregate, combining all tool snapshots.

| Field | Type | Description |
|---|---|---|
| `generated_at` | `datetime` (UTC-aware) | Timestamp when the report was generated |
| `snapshots` | `Dict[str, ToolSnapshot]` | Keyed by tool name string (e.g., `"claude_code"`). Only tools for which at least one session was found are included. |
| `total_sessions_all_tools` | `int` | Derived: sum of `snapshot.total_sessions` across all entries in `snapshots` |
| `total_messages_all_tools` | `int` | Derived: sum of `snapshot.total_messages` across all entries in `snapshots` |

---

## Categorization Model

### `CategoryRule`

Defines one of the fixed topic buckets used to classify sessions.

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Human-readable category name used in the report (e.g., `"Debugging"`) |
| `keywords` | `List[str]` | Keyword and phrase list. Each entry is matched as a case-insensitive substring against the concatenated text of all user messages in a session. |
| `priority` | `int` | Tie-breaking order. When two categories achieve the same score, the one with the lower `priority` value wins. `1` = highest priority. |

### Fixed Categories

The seven categories are fixed and defined at implementation time. They are not configurable by
the user.

| Priority | Name | Keywords |
|---|---|---|
| 1 | Debugging | `error`, `bug`, `fix`, `crash`, `exception`, `traceback`, `fail`, `broken`, `not working`, `issue`, `problem`, `undefined`, `null`, `stack trace` |
| 2 | Code Generation | `create`, `generate`, `write`, `implement`, `add`, `build`, `function`, `class`, `method`, `script`, `boilerplate` |
| 3 | Learning/Explanation | `explain`, `how does`, `what is`, `understand`, `why`, `learn`, `difference between`, `what are`, `tutorial`, `example` |
| 4 | Planning | `design`, `architecture`, `plan`, `approach`, `should i`, `best way`, `strategy`, `tradeoff`, `decision`, `consider` |
| 5 | Writing/Docs | `documentation`, `readme`, `comment`, `docstring`, `document`, `write up`, `description`, `spec` |
| 6 | Refactoring | `refactor`, `clean up`, `improve`, `rename`, `reorganize`, `simplify`, `restructure`, `extract`, `dedup` |
| 7 | Other | (no keywords — assigned when all category scores are zero) |

### Scoring algorithm

1. Concatenate the `content` of all user messages in the session into a single lowercased string.
2. For each `CategoryRule` (in any order), count the total number of keyword/phrase substring
   matches in the concatenated string. This is the category's raw score.
3. Select the `CategoryRule` with the highest score. If multiple categories share the highest
   score, select the one with the lowest `priority` value.
4. If all category scores are zero, assign `"Other"`.
5. Write the winning category name to `Session.category`.

---

## Derived Field Notes

Fields marked "Derived" are computed from other fields and are not read from raw source data.
They should be populated during or immediately after parsing, before the session is passed to
any downstream component (categorizer, report generator).

- `Message.char_count`: computed at `Message` construction time.
- `Session.duration_seconds`: computed from `start_time` and `end_time`.
- `Session.message_count`: computed by filtering `messages` to `role == "user"`.
- `Session.inter_message_gaps`: computed by sorting user messages by timestamp and taking
  consecutive differences.
- `Session.is_flow_state`: computed after `inter_message_gaps` is populated.
- `Session.category`: assigned by the categorizer component after all other fields are set.
- `ToolSnapshot.total_sessions`, `total_messages`, `total_input_tokens`, `total_output_tokens`,
  `date_range_start`, `date_range_end`: all computed from the `sessions` list.
- `InsightsReport.total_sessions_all_tools`, `total_messages_all_tools`: computed from `snapshots`.
