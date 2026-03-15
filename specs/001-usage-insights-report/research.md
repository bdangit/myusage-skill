# Research & Design Decisions

**Feature**: 001-usage-insights-report
**Status**: Decided

---

## 1. Chart.js Inlining Strategy

**Decision**: Fetch Chart.js 4.x from `https://cdn.jsdelivr.net/npm/chart.js` at report generation
time using Python's `urllib.request`, then embed the full library source inline in a `<script>` tag
in the generated HTML. If the fetch fails for any reason, abort with a clear error message.

**Rationale**: This keeps the report entirely self-contained — once generated, the HTML file opens
correctly in any browser with no internet access and no local server. The network call happens once
at generation time, not every time the report is viewed. The user is already online when running the
skill, so the one-time fetch is an acceptable constraint.

**Alternative considered**: Bundle Chart.js source directly in the skill repository. Rejected because
it adds a large (~200 KB minified) binary asset to version control, the bundled copy cannot receive
security patches without a manual update, and it conflates the skill's own code with a third-party
library.

---

## 2. Categorization Strategy

**Decision**: Keyword scoring. Each category has a weighted keyword list. For each session, score
it against every category by summing the number of keyword hits across all user message text
(case-insensitive substring match). Assign the session to the highest-scoring category. Ties go to
the category with the lowest priority value (i.e., listed first in the priority order below).
Sessions with a zero score across all categories are assigned to "Other".

**Categories and keyword lists**:

| Category | Priority | Keywords |
|---|---|---|
| Debugging | 1 | error, bug, fix, crash, exception, traceback, fail, broken, not working, issue, problem, undefined, null, stack trace |
| Code Generation | 2 | create, generate, write, implement, add, build, function, class, method, script, boilerplate |
| Learning/Explanation | 3 | explain, how does, what is, understand, why, learn, difference between, what are, tutorial, example |
| Planning | 4 | design, architecture, plan, approach, should i, best way, strategy, tradeoff, decision, consider |
| Writing/Docs | 5 | documentation, readme, comment, docstring, document, write up, description, spec |
| Refactoring | 6 | refactor, clean up, improve, rename, reorganize, simplify, restructure, extract, dedup |
| Other | 7 | (catch-all — no keywords, assigned when all scores are zero) |

**Rationale**: Simple, deterministic, and fast. Zero external dependencies, no network calls, and
no model API invocations required. Suitable for personal-use bucketing where rough categorization
is more useful than precision.

**Alternative considered**: LLM-based classification — send message content to a model API and
return a category label. Rejected because it requires an external API call (violates FR-007 zero
runtime dependency rule), adds latency, requires credentials, and is overkill for personal
bucketing into seven broad buckets.

---

## 3. Copilot CLI Event Chain

**Decision**: Ignore the `parentId` chain. Read each `events.jsonl` file, filter events by
relevant types (`session.start`, `session.shutdown`, `user.message`, `assistant.usage`,
`session.mode_changed`), and sort all retained events by their timestamp field. Use this flat,
chronological sequence to derive session metrics: turn count, duration, token totals, and mode.

**Relevant event types and what they provide**:

| Event type | Fields used |
|---|---|
| `session.start` | `sessionId`, `startTime`, `selectedModel`, `context.cwd` |
| `session.shutdown` | `totalApiDurationMs`, `modelMetrics` (token totals) |
| `session.mode_changed` | `newMode` (to capture final/dominant mode) |
| `user.message` | `content` (for categorization), `agentMode` (boolean), timestamp |
| `assistant.usage` | `model`, `inputTokens`, `outputTokens` |

The `parentId` field links subagent tool-call events into a tree. This tree structure is useful for
reconstructing which tool calls belong to which turn, but is not needed for the linear metrics this
report computes (session count, duration, message count, token totals).

**Rationale**: Simplicity. The flat chronological sequence contains all the data needed.
Following the `parentId` chain would add significant parsing complexity.

**Alternative considered**: Follow the `parentId` chain to reconstruct the full turn tree, then
aggregate per-turn metrics. Rejected because it adds complexity with no benefit for the timing and
count metrics this report produces. Can be revisited if per-tool-call breakdown is added later.

---

## 4. Session Boundary Detection for Claude Code

**Decision**: Group JSONL entries by the `sessionId` field, which is present on every entry.
Session `start_time` = `min(timestamp)` across all entries with a matching `sessionId`. Session
`end_time` = `max(timestamp)` across the same group.

**Rationale**: Claude Code does not emit explicit `session.start` or `session.end` events. Every
entry already carries a `sessionId`, so grouping by that field is both the natural and most
reliable boundary detection approach. It requires no heuristics about file names or timestamp
gaps.

**Note on file names**: Each JSONL file is named `<session-uuid>.jsonl`, so the file name itself
is the session ID. However, reading from the `sessionId` field is preferred over parsing the file
name because it is explicit data rather than an inferred structural convention.

**Alternative considered**: Infer session boundaries from timestamp gaps (e.g., gap > N minutes
between entries = new session). Rejected because `sessionId` is already provided and unambiguous,
making gap-based inference unnecessary and potentially incorrect for long pauses within a session.

---

## 5. Timezone Handling

**Decision**: Parse all timestamps to UTC-aware `datetime` objects immediately on read, at the
parser layer. Downstream code always operates on UTC-aware datetimes.

**Source-specific parsing**:

| Source | Timestamp format | Parsing approach |
|---|---|---|
| Claude Code | ISO 8601 with `Z` suffix (e.g., `2026-03-14T10:23:00Z`) | `datetime.fromisoformat()` with `Z` → `+00:00` substitution on Python < 3.11, or direct parse on 3.11+ |
| Copilot VS Code | Unix milliseconds (integer, no timezone) | Divide by 1000, `datetime.utcfromtimestamp()`, attach `timezone.utc` |
| Copilot CLI | ISO 8601 with `Z` suffix | Same as Claude Code |

**Rationale**: Normalising to UTC at read time prevents any risk of comparison bugs when mixing
timestamps from different sources — for example, when computing inter-tool statistics or building
a unified hourly heatmap. A single `datetime` type with a consistent timezone throughout the
pipeline is simpler to reason about than conditionally-aware objects.

**Alternative considered**: Store raw strings and parse lazily at comparison time. Rejected because
it spreads timezone logic throughout the codebase and creates subtle bugs when timestamps from
different tools are compared.
