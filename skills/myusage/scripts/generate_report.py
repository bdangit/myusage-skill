#!/usr/bin/env python3
"""
generate_report.py — AI Usage Insights Report Generator

Scans local chat history from Claude Code, Copilot VS Code, and Copilot CLI,
then produces a self-contained HTML report with Charts.js visualizations.

Usage:
    python scripts/generate_report.py [OPTIONS]

Exit codes:
    0 — success
    1 — no data found
    2 — error (parse failure, network failure, write failure)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import glob as glob_module
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import urllib.request
import urllib.error
import sqlite3


# ---------------------------------------------------------------------------
# Platform Constants
# ---------------------------------------------------------------------------

# Codex session database location — highest version number takes precedence
CODEX_HOME_DIR = Path.home() / ".codex"
CODEX_DB_PATTERN = "state_*.sqlite"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Message:
    timestamp: datetime
    role: str
    content: str
    char_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.char_count = len(self.content)


@dataclass
class Session:
    session_id: str
    tool: str
    project_path: Optional[str]
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    messages: List[Message]
    message_count: int
    model: Optional[str]
    mode: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    category: str = "Other"
    tool_call_count: int = 0
    session_character: str = "general"
    inter_message_gaps: List[float] = field(default_factory=list)
    character_approximate: bool = False
    model_request_counts: Optional[Dict[str, int]] = None
    model_token_totals: Optional[Dict[str, Dict[str, int]]] = None
    effective_prus: Optional[float] = None
    estimated_cost_usd: Optional[float] = None
    cost_breakdown_available: bool = True  # False for Codex (only total tokens available)
    total_tokens: Optional[int] = None  # Used by Codex (combined input+output)


@dataclass
class ToolSnapshot:
    tool: str
    sessions: List[Session]
    total_sessions: int
    total_messages: int
    total_input_tokens: Optional[int]
    total_output_tokens: Optional[int]
    date_range_start: datetime
    date_range_end: datetime


@dataclass
class InsightsReport:
    generated_at: datetime
    local_timezone: str
    snapshots: Dict[str, ToolSnapshot]
    total_sessions_all_tools: int
    total_messages_all_tools: int
    peak_concurrent_sessions: int
    avg_concurrent_sessions: float


# ---------------------------------------------------------------------------
# Cost tables  (edit these when vendors update pricing)
# ---------------------------------------------------------------------------

# PRU multipliers per Copilot model — last verified: 2026-03-17
# Copilot surfaces model IDs in two forms: plain ("claude-haiku-4.5") and
# namespaced ("copilot/claude-haiku-4.5"). Both are listed here.
PRU_MULTIPLIERS: Dict[str, float] = {
    "gpt-4o":                       1.0,
    "gpt-4o-mini":                  1.0,
    "gpt-5":                        1.0,
    "gpt-5-mini":                   1.0,
    "o3-mini":                      1.0,
    "claude-haiku-4.5":             1.0,
    "copilot/claude-haiku-4.5":     1.0,
    "claude-sonnet-4-6":            1.0,
    "copilot/claude-sonnet-4-6":    1.0,
    "claude-opus-4-6":              3.0,
    "copilot/claude-opus-4-6":      3.0,
    "gemini-2.0-flash":             1.0,
    "copilot/gemini-2.0-flash":     1.0,
}
PRU_DEFAULT_MULTIPLIER: float = 1.0
PRU_UNIT_PRICE_USD: float = 0.04  # USD per effective PRU at list price

# Token prices in USD per million tokens — last verified: 2026-03-17
TOKEN_PRICES: Dict[str, Dict[str, float]] = {
    "claude-haiku-4.5":  {"input": 0.80,  "output": 4.00},
    "claude-sonnet-4-6": {"input": 3.00,  "output": 15.00},
    "claude-opus-4-6":   {"input": 15.00, "output": 75.00},
}


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

def _parse_iso_z(ts: str) -> datetime:
    """Parse ISO 8601 timestamps with Z suffix — compatible with Python 3.8+."""
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


def _parse_unix_ms(ms: int) -> datetime:
    """Parse Unix millisecond timestamp to UTC-aware datetime."""
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)


def _parse_unix_seconds(seconds: int) -> datetime:
    """Parse Unix second timestamp to UTC-aware datetime."""
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def _map_permission_mode(pm: Optional[str]) -> str:
    """Map Claude Code permissionMode field to a canonical mode string."""
    if pm == "plan":
        return "plan"
    if pm == "acceptEdits":
        return "edit"
    return "default"


# ---------------------------------------------------------------------------
# Parser: Claude Code
# ---------------------------------------------------------------------------

def parse_claude_code(claude_dir: str) -> List[Session]:
    """
    Scan claude_dir recursively for *.jsonl files, excluding 'subagents' subdirs.
    Group entries by sessionId; build Session objects.
    """
    claude_dir = os.path.expanduser(claude_dir)
    if not os.path.isdir(claude_dir):
        return []

    # Find all JSONL files, skip those in a 'subagents' directory
    jsonl_files: List[str] = []
    for root, dirs, files in os.walk(claude_dir):
        # Prune subagents directories
        dirs[:] = [d for d in dirs if d != "subagents"]
        for fname in files:
            if fname.endswith(".jsonl"):
                jsonl_files.append(os.path.join(root, fname))

    # Map sessionId -> list of raw entries
    sessions_raw: Dict[str, List[dict]] = {}

    for fpath in jsonl_files:
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError as exc:
                        print(
                            f"Warning: skipping malformed JSON in {fpath} line {lineno}: {exc}",
                            file=sys.stderr,
                        )
                        continue
                    sid = entry.get("sessionId")
                    if not sid:
                        continue
                    sessions_raw.setdefault(sid, []).append(entry)
        except OSError as exc:
            print(f"Warning: cannot read {fpath}: {exc}", file=sys.stderr)

    sessions: List[Session] = []
    for sid, entries in sessions_raw.items():
        messages: List[Message] = []
        tool_call_count = 0
        model: Optional[str] = None
        input_tokens_total = 0
        output_tokens_total = 0
        model_token_totals: Dict[str, Dict[str, int]] = {}
        has_token_data = False
        project_path: Optional[str] = None
        permission_mode: Optional[str] = None  # first permissionMode seen on user entries

        for entry in entries:
            entry_type = entry.get("type", "")
            ts_str = entry.get("timestamp", "")
            if not ts_str:
                continue
            try:
                ts = _parse_iso_z(ts_str)
            except (ValueError, TypeError):
                continue

            # Capture permissionMode from user entries (top-level field)
            if permission_mode is None and entry_type == "user":
                raw_pm = entry.get("permissionMode")
                if raw_pm is not None:
                    permission_mode = raw_pm

            if entry_type == "user":
                msg_obj = entry.get("message", {})
                content_raw = msg_obj.get("content", "")
                if isinstance(content_raw, list):
                    # Skip entries that are purely tool_result blocks — these are
                    # tool responses fed back to the model, not real human messages.
                    block_types = {
                        block.get("type")
                        for block in content_raw
                        if isinstance(block, dict)
                    }
                    if block_types and block_types <= {"tool_result"}:
                        if not project_path:
                            project_path = entry.get("cwd")
                        continue
                    parts = []
                    for block in content_raw:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            parts.append(block)
                    content = " ".join(parts)
                else:
                    content = str(content_raw)
                messages.append(Message(timestamp=ts, role="user", content=content))
                if not project_path:
                    project_path = entry.get("cwd")

            elif entry_type == "assistant":
                msg_obj = entry.get("message", {})
                # Model
                entry_model = msg_obj.get("model")
                if not model:
                    model = entry_model
                # Tokens
                usage = msg_obj.get("usage", {})
                in_tok = usage.get("input_tokens")
                out_tok = usage.get("output_tokens")
                if in_tok is not None:
                    input_tokens_total += int(in_tok)
                    has_token_data = True
                if out_tok is not None:
                    output_tokens_total += int(out_tok)
                if entry_model and (in_tok is not None or out_tok is not None):
                    model_totals = model_token_totals.setdefault(
                        entry_model, {"input_tokens": 0, "output_tokens": 0}
                    )
                    if in_tok is not None:
                        model_totals["input_tokens"] += int(in_tok)
                    if out_tok is not None:
                        model_totals["output_tokens"] += int(out_tok)

                # Tool use blocks
                content_list = msg_obj.get("content", [])
                if isinstance(content_list, list):
                    for block in content_list:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            tool_call_count += 1
                # Also add assistant message
                assistant_text = ""
                if isinstance(content_list, list):
                    for block in content_list:
                        if isinstance(block, dict) and block.get("type") == "text":
                            assistant_text += block.get("text", "")
                elif isinstance(content_list, str):
                    assistant_text = content_list
                messages.append(Message(timestamp=ts, role="assistant", content=assistant_text))

        if not messages:
            continue

        user_msgs = [m for m in messages if m.role == "user"]
        if not user_msgs:
            continue

        all_ts = [m.timestamp for m in messages]
        start_time = min(all_ts)
        end_time = max(all_ts)
        duration_seconds = (end_time - start_time).total_seconds()

        gaps = compute_inter_message_gaps(user_msgs)

        session = Session(
            session_id=sid,
            tool="claude_code",
            project_path=project_path,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration_seconds,
            messages=messages,
            message_count=len(user_msgs),
            model=model,
            mode=_map_permission_mode(permission_mode),
            input_tokens=input_tokens_total if has_token_data else None,
            output_tokens=output_tokens_total if has_token_data else None,
            tool_call_count=tool_call_count,
            inter_message_gaps=gaps,
            character_approximate=False,
            model_token_totals=model_token_totals if model_token_totals else None,
        )
        char, approx = classify_session_character(session)
        session.session_character = char
        session.character_approximate = approx
        session.category = categorize_session(session)
        sessions.append(session)

    return sessions


# ---------------------------------------------------------------------------
# Parser: Copilot VS Code
# ---------------------------------------------------------------------------

def parse_copilot_vscode(vscode_dir: str) -> List[Session]:
    """
    Scan vscode_dir for */chatSessions/*.json files.
    Each file is one session.
    """
    vscode_dir = os.path.expanduser(vscode_dir)
    if not os.path.isdir(vscode_dir):
        return []

    pattern = os.path.join(vscode_dir, "*", "chatSessions", "*.json")
    json_files = glob_module.glob(pattern)

    sessions: List[Session] = []
    for fpath in json_files:
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Warning: cannot read {fpath}: {exc}", file=sys.stderr)
            continue

        session_id = data.get("sessionId", os.path.basename(fpath))
        creation_date_ms = data.get("creationDate")
        last_msg_date_ms = data.get("lastMessageDate")

        # Mode
        input_state = data.get("inputState", {})
        mode_obj = input_state.get("mode", {})
        raw_mode = mode_obj.get("id")
        mode = raw_mode if raw_mode in ("agent", "ask", "autopilot") else None

        # Model
        selected_model = input_state.get("selectedModel", {})
        model_meta = selected_model.get("metadata", {})
        model = model_meta.get("id") or data.get("modelId") or None

        requests = data.get("requests", [])
        messages: List[Message] = []
        req_model_counts: Dict[str, int] = {}

        for req in requests:
            ts_ms = req.get("timestamp")
            if ts_ms is None:
                continue
            try:
                ts = _parse_unix_ms(int(ts_ms))
            except (ValueError, TypeError):
                continue

            # User message from parts
            msg_obj = req.get("message", {})
            parts = msg_obj.get("parts", [])
            text_parts = []
            for part in parts:
                if isinstance(part, dict):
                    t = part.get("text", "")
                    if t:
                        text_parts.append(t)
            content = " ".join(text_parts)
            messages.append(Message(timestamp=ts, role="user", content=content))

            # Track per-request model for accurate PRU calculation
            req_model = req.get("modelId")
            if req_model:
                req_model_counts[req_model] = req_model_counts.get(req_model, 0) + 1
                if not model:
                    model = req_model

        if not messages:
            # Try to synthesize start/end from session-level fields
            if creation_date_ms is not None:
                try:
                    ts = _parse_unix_ms(int(creation_date_ms))
                    messages.append(Message(timestamp=ts, role="user", content=""))
                except (ValueError, TypeError):
                    pass

        if not messages:
            continue

        user_msgs = [m for m in messages if m.role == "user"]
        all_ts = [m.timestamp for m in messages]

        if creation_date_ms is not None:
            try:
                start_time = _parse_unix_ms(int(creation_date_ms))
            except (ValueError, TypeError):
                start_time = min(all_ts)
        else:
            start_time = min(all_ts)

        if last_msg_date_ms is not None:
            try:
                end_time = _parse_unix_ms(int(last_msg_date_ms))
            except (ValueError, TypeError):
                end_time = max(all_ts)
        else:
            end_time = max(all_ts)

        if end_time < start_time:
            end_time = max(all_ts)

        duration_seconds = (end_time - start_time).total_seconds()
        gaps = compute_inter_message_gaps(user_msgs)

        session = Session(
            session_id=session_id,
            tool="copilot_vscode",
            project_path=None,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration_seconds,
            messages=messages,
            message_count=len(user_msgs),
            model=model,
            mode=mode,
            input_tokens=None,
            output_tokens=None,
            tool_call_count=0,
            inter_message_gaps=gaps,
            character_approximate=True,  # tool_call_count not available
            model_request_counts=req_model_counts if req_model_counts else None,
        )
        char, approx = classify_session_character(session)
        session.session_character = char
        session.character_approximate = approx
        session.category = categorize_session(session)
        sessions.append(session)

    return sessions


# ---------------------------------------------------------------------------
# Parser: Copilot CLI
# ---------------------------------------------------------------------------

def parse_copilot_cli(cli_dir: str) -> List[Session]:
    """
    Scan cli_dir for */events.jsonl files.
    Filter by relevant event types; build Session objects.
    """
    cli_dir = os.path.expanduser(cli_dir)
    if not os.path.isdir(cli_dir):
        return []

    pattern = os.path.join(cli_dir, "*", "events.jsonl")
    jsonl_files = glob_module.glob(pattern)

    sessions: List[Session] = []

    for fpath in jsonl_files:
        events: List[dict] = []
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        print(
                            f"Warning: skipping malformed JSON in {fpath} line {lineno}: {exc}",
                            file=sys.stderr,
                        )
        except OSError as exc:
            print(f"Warning: cannot read {fpath}: {exc}", file=sys.stderr)
            continue

        session_id: Optional[str] = None
        project_path: Optional[str] = None
        start_time: Optional[datetime] = None
        end_time: Optional[datetime] = None
        model: Optional[str] = None
        mode: Optional[str] = None
        input_tokens_total = 0
        output_tokens_total = 0
        has_token_data = False
        tool_call_count = 0
        messages: List[Message] = []
        model_request_counts: Dict[str, int] = {}
        total_pru: float = 0.0
        has_pru_data = False

        for ev in events:
            ev_type = ev.get("type", "")
            data = ev.get("data", ev)  # some schemas put payload in data, some flat

            if ev_type == "session.start":
                session_id = data.get("sessionId") or ev.get("sessionId")
                ts_str = data.get("startTime") or ev.get("startTime")
                if ts_str:
                    try:
                        start_time = _parse_iso_z(ts_str)
                    except (ValueError, TypeError):
                        pass
                if not model:
                    model = data.get("selectedModel") or ev.get("selectedModel")
                context = data.get("context", ev.get("context", {}))
                if isinstance(context, dict):
                    project_path = context.get("cwd")

            elif ev_type == "session.shutdown":
                ts_str = data.get("endTime") or ev.get("endTime") or data.get("sessionStartTime") or ev.get("sessionStartTime")
                # Try to get end time from model metrics or just use last known
                # We'll derive end_time from last message timestamp
                pru_val = data.get("totalPremiumRequests")
                if pru_val is None:
                    pru_val = ev.get("totalPremiumRequests")
                if pru_val is not None:
                    try:
                        total_pru = float(pru_val)
                        has_pru_data = True
                    except (TypeError, ValueError):
                        pass

            elif ev_type == "session.mode_changed":
                new_mode = data.get("newMode") or ev.get("newMode")
                if new_mode:
                    mode = "agent" if str(new_mode).lower() in ("agent", "agentic", "true") else "ask"

            elif ev_type == "user.message":
                content = data.get("content") or ev.get("content", "")
                agent_mode = data.get("agentMode") if "agentMode" in data else ev.get("agentMode")
                ts_str = data.get("timestamp") or ev.get("timestamp")
                if ts_str:
                    try:
                        ts = _parse_iso_z(str(ts_str))
                    except (ValueError, TypeError):
                        ts = start_time or datetime.now(tz=timezone.utc)
                else:
                    ts = start_time or datetime.now(tz=timezone.utc)

                if mode is None and agent_mode is not None:
                    mode = "agent" if agent_mode else "ask"

                messages.append(Message(timestamp=ts, role="user", content=str(content)))

            elif ev_type == "assistant.usage":
                ev_model = data.get("model") or ev.get("model")
                if ev_model:
                    if not model:
                        model = ev_model
                    model_request_counts[ev_model] = model_request_counts.get(ev_model, 0) + 1
                in_tok = data.get("inputTokens") or ev.get("inputTokens")
                out_tok = data.get("outputTokens") or ev.get("outputTokens")
                if in_tok is not None:
                    input_tokens_total += int(in_tok)
                    has_token_data = True
                if out_tok is not None:
                    output_tokens_total += int(out_tok)

                # timestamp
                ts_str = data.get("timestamp") or ev.get("timestamp")
                if ts_str:
                    try:
                        ts = _parse_iso_z(str(ts_str))
                        messages.append(Message(timestamp=ts, role="assistant", content=""))
                    except (ValueError, TypeError):
                        pass

            elif ev_type == "tool.execution_start":
                tool_call_count += 1

        if not messages:
            continue

        user_msgs = [m for m in messages if m.role == "user"]
        if not user_msgs:
            continue

        if not session_id:
            session_id = os.path.basename(os.path.dirname(fpath))

        all_ts = [m.timestamp for m in messages]
        if start_time is None:
            start_time = min(all_ts)
        actual_end = max(all_ts)
        end_time = actual_end

        duration_seconds = (end_time - start_time).total_seconds()
        gaps = compute_inter_message_gaps(user_msgs)

        session = Session(
            session_id=session_id,
            tool="copilot_cli",
            project_path=project_path,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration_seconds,
            messages=messages,
            message_count=len(user_msgs),
            model=model,
            mode=mode,
            input_tokens=input_tokens_total if has_token_data else None,
            output_tokens=output_tokens_total if has_token_data else None,
            tool_call_count=tool_call_count,
            inter_message_gaps=gaps,
            character_approximate=False,
            model_request_counts=model_request_counts if model_request_counts else None,
            effective_prus=total_pru if has_pru_data else None,
        )
        char, approx = classify_session_character(session)
        session.session_character = char
        session.character_approximate = approx
        session.category = categorize_session(session)
        sessions.append(session)

    return sessions


# ---------------------------------------------------------------------------
# Parser: Codex
# ---------------------------------------------------------------------------

def discover_codex_database() -> Optional[Path]:
    """
    Search ~/.codex/ for files matching state_*.sqlite.
    Return the highest-numbered version (e.g., prefer state_5.sqlite over state_4.sqlite).
    Return None if no database files found.
    On error (permission denied, etc.), log a warning to stderr and return None.
    """
    if not CODEX_HOME_DIR.exists():
        return None
    
    try:
        db_files = list(CODEX_HOME_DIR.glob(CODEX_DB_PATTERN))
        if not db_files:
            return None
        
        # Extract version numbers and sort
        def extract_version(p: Path) -> int:
            try:
                # state_5.sqlite -> 5
                stem = p.stem  # "state_5"
                parts = stem.split("_")
                if len(parts) == 2 and parts[0] == "state":
                    return int(parts[1])
                return 0
            except (ValueError, IndexError):
                return 0
        
        db_files.sort(key=extract_version, reverse=True)
        return db_files[0]
    
    except (OSError, PermissionError) as exc:
        print(f"Warning: cannot access Codex database directory: {exc}", file=sys.stderr)
        return None


def extract_model_from_rollout(rollout_path: Path) -> Optional[str]:
    """
    Open the JSONL file at rollout_path.
    Iterate through lines (one JSON object per line).
    Find the first turn_context event.
    Extract and return the model field (or equivalent model name field).
    If not found or file is missing/corrupted, log a warning and return None.
    Handle exceptions gracefully (return None on parse errors).
    """
    if not rollout_path.exists():
        return None
    
    try:
        with open(rollout_path, "r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if event.get("type") == "turn_context":
                        model = event.get("model")
                        if model:
                            return model
                except json.JSONDecodeError as exc:
                    print(
                        f"Warning: skipping malformed JSON in {rollout_path} line {lineno}: {exc}",
                        file=sys.stderr,
                    )
                    continue
        return None
    except OSError as exc:
        print(f"Warning: cannot read rollout file {rollout_path}: {exc}", file=sys.stderr)
        return None


def count_user_messages_in_rollout(rollout_path: Path) -> int:
    """
    Open the JSONL file at rollout_path.
    Iterate through lines.
    Count response_item events where role == "user" and message contains non-system text.
    Return the count (default to 0 if file missing or corrupted).
    Log warnings on parse errors but do not raise.
    """
    if not rollout_path.exists():
        return 0
    
    count = 0
    try:
        with open(rollout_path, "r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if event.get("type") == "response_item":
                        if event.get("role") == "user":
                            # Check for non-system text
                            content = event.get("content", "")
                            if content and not _is_system_message(content):
                                count += 1
                except json.JSONDecodeError as exc:
                    print(
                        f"Warning: skipping malformed JSON in {rollout_path} line {lineno}: {exc}",
                        file=sys.stderr,
                    )
                    continue
    except OSError as exc:
        print(f"Warning: cannot read rollout file {rollout_path}: {exc}", file=sys.stderr)
        return 0
    
    return count


def extract_first_user_message_from_rollout(rollout_path: Path) -> str:
    """
    Extract the first user message from the rollout file for categorization.
    Return empty string if not found.
    """
    if not rollout_path.exists():
        return ""
    
    try:
        with open(rollout_path, "r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if event.get("type") == "response_item":
                        if event.get("role") == "user":
                            content = event.get("content", "")
                            if content and not _is_system_message(content):
                                return content
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    
    return ""


def parse_codex_database(db_path: Path) -> List[Session]:
    """
    Connect to SQLite database at db_path.
    Query the threads table.
    For each row, extract session metadata (id, created_at, updated_at, cwd,
    tokens_used, cli_version, source, approval_mode, rollout_path).
    If model field is NULL, resolve via extract_model_from_rollout() using the rollout_path from the row.
    Call count_user_messages_in_rollout() to populate user_message_count.
    Extract first_user_message from the rollout file.
    Return a list of Session objects (with tool="codex").
    On database error (corrupted, locked, schema mismatch), log a warning and return an empty list.
    """
    if not db_path.exists():
        print(f"Warning: Codex database not found at {db_path}", file=sys.stderr)
        return []
    
    sessions: List[Session] = []
    
    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Query threads table
            cursor.execute("""
                SELECT id, created_at, updated_at, cwd, tokens_used, 
                       model, cli_version, source, approval_mode, rollout_path
                FROM threads
            """)
            
            for row in cursor.fetchall():
                session_id = row["id"]
                created_at_str = row["created_at"]
                updated_at_str = row["updated_at"]
                working_directory = row["cwd"]
                tokens_used = row["tokens_used"] or 0
                model = row["model"]
                cli_version = row["cli_version"]
                source = row["source"]
                approval_mode = row["approval_mode"]
                rollout_path_str = row["rollout_path"]
                
                # Parse timestamps - handle both ISO Z format (string) and Unix timestamps (int)
                try:
                    if isinstance(created_at_str, int):
                        start_time = _parse_unix_seconds(created_at_str)
                    else:
                        start_time = _parse_iso_z(created_at_str)
                    
                    if isinstance(updated_at_str, int):
                        end_time = _parse_unix_seconds(updated_at_str)
                    else:
                        end_time = _parse_iso_z(updated_at_str)
                except (ValueError, TypeError):
                    print(f"Warning: invalid timestamps for Codex session {session_id}", file=sys.stderr)
                    continue
                
                # Resolve model if NULL
                if rollout_path_str:
                    # rollout_path may be absolute or relative to the database directory
                    rollout_path = Path(rollout_path_str)
                    if not rollout_path.is_absolute():
                        rollout_path = db_path.parent / rollout_path
                else:
                    rollout_path = None
                
                if not model and rollout_path:
                    model = extract_model_from_rollout(rollout_path)
                
                # Count user messages
                user_message_count = 0
                first_user_message = ""
                if rollout_path:
                    user_message_count = count_user_messages_in_rollout(rollout_path)
                    first_user_message = extract_first_user_message_from_rollout(rollout_path)
                
                # Build a minimal message list for compatibility
                # We create placeholder messages to satisfy the Session dataclass
                duration_seconds = (end_time - start_time).total_seconds()
                
                # Create messages based on user_message_count
                messages: List[Message] = []
                if user_message_count > 0:
                    # Add first user message if available
                    if first_user_message:
                        messages.append(Message(timestamp=start_time, role="user", content=first_user_message))
                    else:
                        # Create placeholder with empty content to maintain count
                        messages.append(Message(timestamp=start_time, role="user", content=""))
                    
                    # Add placeholders for remaining messages
                    for i in range(1, user_message_count):
                        # Distribute messages evenly across the session duration
                        msg_time = start_time + timedelta(seconds=(duration_seconds * i / user_message_count))
                        messages.append(Message(timestamp=msg_time, role="user", content=""))
                
                # Compute inter-message gaps
                user_msgs = [m for m in messages if m.role == "user"]
                gaps = compute_inter_message_gaps(user_msgs)
                
                # Create Session object
                session = Session(
                    session_id=session_id,
                    tool="codex",
                    project_path=working_directory,
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=duration_seconds,
                    messages=messages,
                    message_count=user_message_count,
                    model=model,
                    mode=approval_mode,
                    input_tokens=None,  # Codex only provides total tokens
                    output_tokens=None,
                    tool_call_count=0,  # Not available in Codex database
                    inter_message_gaps=gaps,
                    character_approximate=True,  # No tool_call data available
                    cost_breakdown_available=False,  # Codex only has total tokens, no input/output split
                    total_tokens=tokens_used if tokens_used > 0 else None,  # Combined token count from Codex
                )
                
                # Apply categorization and character classification
                char, approx = classify_session_character(session)
                session.session_character = char
                session.character_approximate = approx
                session.category = categorize_codex_session(session)
                
                sessions.append(session)
        
    except sqlite3.Error as exc:
        print(f"Warning: cannot read Codex database at {db_path}: {exc}", file=sys.stderr)
        return []
    except Exception as exc:
        print(f"Warning: unexpected error parsing Codex database: {exc}", file=sys.stderr)
        return []
    
    return sessions


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------

def classify_session_character(session: Session) -> Tuple[str, bool]:
    """
    Implement data-model.md session character rules.
    Returns (character, is_approximate).
    """
    mc = session.message_count
    tc = session.tool_call_count
    dur = session.duration_seconds
    gaps = session.inter_message_gaps
    approx = session.character_approximate

    if approx:
        # Fallback: no tool_call data (Copilot VS Code)
        if dur >= 600 and mc <= 3:
            return ("autonomous", True)
        median_gap = statistics.median(gaps) if gaps else float("inf")
        if mc >= 5 and median_gap < 120:
            return ("deeply_engaged", True)
        return ("general", True)
    else:
        # Full logic
        ratio = tc / max(mc, 1)
        if ratio >= 3 and dur >= 300:
            return ("autonomous", False)
        median_gap = statistics.median(gaps) if gaps else float("inf")
        if mc >= 5 and median_gap < 120 and ratio < 1:
            return ("deeply_engaged", False)
        return ("general", False)


# Category rules as (name, priority, keywords)
# Keywords are deliberately distinctive — generic verbs like "write", "create", "add"
# are excluded from Code Generation to avoid misclassifying doc/spec/review work.
CATEGORY_RULES = [
    ("Debugging", 1, [
        "error", "bug", "fix", "crash", "exception", "traceback", "fail",
        "broken", "not working", "undefined", "null", "stack trace",
        "doesn't work", "failing", "wrong output", "incorrect", "unexpected"
    ]),
    ("Code Generation", 2, [
        "implement", "function", "class", "method", "boilerplate",
        "endpoint", "api", "test", "schema", "component",
        "module", "library", "cli", "pipeline", "database", "query",
        "scaffold", "bootstrap", "migration"
    ]),
    ("Writing/Docs", 3, [
        "document", "documentation", "readme", "spec", "proposal",
        "review", "revise", "edit", "draft", "write up", "summarize",
        "summary", "report", "resume", "notes", "checklist", "email",
        "description", "docstring", "comment", "proofread", "feedback",
        "template", "brief", "outline", "charter", "constitution"
    ]),
    ("Setup & Config", 4, [
        "configure", "configuration", "setup", "install", "settings",
        "config", "statusline", "autopilot", "enable", "preference",
        "dotfiles", "environment", "agents.md", "claude.md", "hook",
        "permission", "mcp", "extension", "plugin", "keybinding"
    ]),
    ("Infrastructure", 5, [
        "vm", "docker", "container", "server", "provision", "host",
        "isolated", "instance", "self-host", "deploy", "networking",
        "nginx", "php", "podman", "lima", "virtual machine", "port"
    ]),
    ("Research & Analysis", 6, [
        "research", "analyze", "analysis", "tax", "financial", "finance",
        "business", "permit", "insurance", "pricing", "roi", "spreadsheet",
        "budget", "revenue", "cost", "market", "compare", "evaluate",
        "assessment", "audit", "review options"
    ]),
    ("Learning/Explanation", 7, [
        "explain", "how does", "what is", "understand", "why", "learn",
        "difference between", "what are", "tutorial", "example",
        "how do i", "show me", "walk me through", "what does"
    ]),
    ("Planning", 8, [
        "design", "architecture", "plan", "approach", "should i", "best way",
        "strategy", "tradeoff", "decision", "consider", "roadmap",
        "prioritize", "scope", "requirements", "breakdown", "steps"
    ]),
    ("Refactoring", 9, [
        "refactor", "clean up", "rename", "reorganize",
        "simplify", "restructure", "extract", "dedup", "consolidate",
        "move", "split", "merge", "optimize"
    ]),
    ("Other", 10, []),
]

# Prefixes that indicate a message is a system/command invocation, not real user content.
# These should be excluded from category scoring.
_SYSTEM_MSG_PREFIXES = (
    "<command-name>", "<command-message>", "<local-command-caveat>",
    "<bash-input>", "<bash-stdout>", "<bash-stderr>", "<system-reminder>",
    "<tool-", "<function_calls>", "</", "<!-",
)


def _is_system_message(content: str) -> bool:
    """Return True if the message is a system/command wrapper, not real user content."""
    stripped = content.strip()
    return any(stripped.startswith(p) for p in _SYSTEM_MSG_PREFIXES)


def categorize_session(session: Session) -> str:
    """Keyword scoring categorization. Skips system/command messages."""
    user_text = " ".join(
        m.content for m in session.messages
        if m.role == "user" and not _is_system_message(m.content)
    ).lower()

    # If no real user content, leave as Other
    if not user_text.strip():
        return "Other"

    best_name = "Other"
    best_score = 0
    best_priority = 999

    for name, priority, keywords in CATEGORY_RULES:
        if not keywords:
            continue
        score = sum(user_text.count(kw) for kw in keywords)
        if score > best_score or (score == best_score and score > 0 and priority < best_priority):
            best_score = score
            best_name = name
            best_priority = priority

    return best_name


def categorize_codex_session(session: Session) -> str:
    """
    Categorize a Codex session using its first user message.
    Codex sessions have a first_user_message extracted from the rollout.
    This function uses keyword scoring on the first message content.
    If no real user content, return "Other".
    """
    # Extract first user message from the Codex session messages
    first_user_msg = None
    for m in session.messages:
        if m.role == "user" and m.content and not _is_system_message(m.content):
            first_user_msg = m.content
            break
    
    if not first_user_msg:
        return "Other"
    
    user_text = first_user_msg.lower()
    
    best_name = "Other"
    best_score = 0
    best_priority = 999
    
    for name, priority, keywords in CATEGORY_RULES:
        if not keywords:
            continue
        score = sum(user_text.count(kw) for kw in keywords)
        if score > best_score or (score == best_score and score > 0 and priority < best_priority):
            best_score = score
            best_name = name
            best_priority = priority
    
    return best_name


def compute_inter_message_gaps(user_messages: List[Message]) -> List[float]:
    """Sort user messages by timestamp, compute consecutive differences in seconds."""
    if len(user_messages) < 2:
        return []
    sorted_msgs = sorted(user_messages, key=lambda m: m.timestamp)
    return [
        (sorted_msgs[i + 1].timestamp - sorted_msgs[i].timestamp).total_seconds()
        for i in range(len(sorted_msgs) - 1)
    ]


def compute_concurrent_sessions(all_sessions: List[Session]) -> Tuple[int, float]:
    """
    Compute peak and average concurrent sessions.
    Peak: sweep-line over start/end events.
    Average: sample at 1-min intervals across full date range.
    """
    if not all_sessions:
        return 0, 0.0

    # Sweep-line for peak
    events: List[Tuple[datetime, int]] = []
    for s in all_sessions:
        events.append((s.start_time, +1))
        events.append((s.end_time, -1))
    events.sort(key=lambda x: (x[0], x[1]))  # ends before starts at same time

    peak = 0
    current = 0
    for _, delta in events:
        current += delta
        if current > peak:
            peak = current

    # Average via 1-minute sampling
    all_start = min(s.start_time for s in all_sessions)
    all_end = max(s.end_time for s in all_sessions)
    total_minutes = int((all_end - all_start).total_seconds() / 60) + 1

    if total_minutes <= 0:
        return peak, 0.0

    total_active = 0
    for i in range(total_minutes):
        sample_time = all_start + timedelta(minutes=i)
        active = sum(
            1 for s in all_sessions
            if s.start_time <= sample_time <= s.end_time
        )
        total_active += active

    avg = total_active / total_minutes
    return peak, avg


def build_report(all_sessions: List[Session]) -> InsightsReport:
    """Group sessions into ToolSnapshot objects; compute InsightsReport."""
    snapshots: Dict[str, ToolSnapshot] = {}

    # Group by tool
    by_tool: Dict[str, List[Session]] = {}
    for s in all_sessions:
        by_tool.setdefault(s.tool, []).append(s)

    for tool, sess_list in by_tool.items():
        total_sessions = len(sess_list)
        total_messages = sum(s.message_count for s in sess_list)

        input_tok_list = [s.input_tokens for s in sess_list if s.input_tokens is not None]
        output_tok_list = [s.output_tokens for s in sess_list if s.output_tokens is not None]
        total_input_tokens = sum(input_tok_list) if input_tok_list else None
        total_output_tokens = sum(output_tok_list) if output_tok_list else None

        date_range_start = min(s.start_time for s in sess_list)
        date_range_end = max(s.end_time for s in sess_list)

        snapshots[tool] = ToolSnapshot(
            tool=tool,
            sessions=sess_list,
            total_sessions=total_sessions,
            total_messages=total_messages,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
        )

    compute_session_costs(all_sessions)

    peak, avg = compute_concurrent_sessions(all_sessions)

    local_tz = datetime.now().astimezone().tzinfo
    local_tz_name = str(local_tz) if local_tz else "UTC"

    return InsightsReport(
        generated_at=datetime.now(tz=timezone.utc),
        local_timezone=local_tz_name,
        snapshots=snapshots,
        total_sessions_all_tools=sum(s.total_sessions for s in snapshots.values()),
        total_messages_all_tools=sum(s.total_messages for s in snapshots.values()),
        peak_concurrent_sessions=peak,
        avg_concurrent_sessions=avg,
    )


def compute_session_costs(sessions: List[Session]) -> None:
    """Mutate sessions in-place to set effective_prus and estimated_cost_usd."""
    for s in sessions:
        s.effective_prus = None
        s.estimated_cost_usd = None

        if s.tool in ("copilot_vscode", "copilot_cli"):
            # Build per-model interaction counts
            if s.model_request_counts:
                counts = s.model_request_counts
            elif s.model:
                counts = {s.model: s.message_count}
            else:
                counts = {}

            if not counts:
                print(
                    f"Warning: no model data for session '{s.session_id}'; cost unknown",
                    file=sys.stderr,
                )
                continue

            total_prus = 0.0
            for model, cnt in counts.items():
                multiplier = PRU_MULTIPLIERS.get(model)
                if multiplier is None:
                    print(
                        f"Warning: no PRU multiplier for model '{model}' in session "
                        f"'{s.session_id}'; using default {PRU_DEFAULT_MULTIPLIER}x",
                        file=sys.stderr,
                    )
                    multiplier = PRU_DEFAULT_MULTIPLIER
                total_prus += cnt * multiplier

            s.effective_prus = total_prus
            s.estimated_cost_usd = total_prus * PRU_UNIT_PRICE_USD

        elif s.tool == "claude_code":
            if s.model_token_totals:
                total_cost = 0.0
                unknown_models: List[str] = []
                for model_name, totals in s.model_token_totals.items():
                    prices = TOKEN_PRICES.get(model_name)
                    if prices is None:
                        unknown_models.append(model_name)
                        continue
                    total_cost += (
                        totals.get("input_tokens", 0) / 1_000_000 * prices["input"]
                        + totals.get("output_tokens", 0) / 1_000_000 * prices["output"]
                    )
                if unknown_models:
                    print(
                        f"Warning: no token price for model(s) {', '.join(repr(m) for m in unknown_models)} "
                        f"in session '{s.session_id}'; cost unknown",
                        file=sys.stderr,
                    )
                    continue
                s.estimated_cost_usd = total_cost
            elif s.input_tokens is not None and s.output_tokens is not None and s.model:
                prices = TOKEN_PRICES.get(s.model)
                if prices is None:
                    print(
                        f"Warning: no token price for model '{s.model}' in session "
                        f"'{s.session_id}'; cost unknown",
                        file=sys.stderr,
                    )
                else:
                    s.estimated_cost_usd = (
                        s.input_tokens / 1_000_000 * prices["input"]
                        + s.output_tokens / 1_000_000 * prices["output"]
                    )


def extract_data(report: InsightsReport, all_sessions: List[Session], days_filter: Optional[int] = None) -> str:
    """
    Extract structured session data as a JSON string for Claude to read and generate insights.
    Returns a pretty-printed JSON string.
    """
    local_tz = datetime.now().astimezone().tzinfo
    local_tz_name = str(local_tz) if local_tz else "UTC"

    def fmt_date_local(dt: datetime) -> str:
        if local_tz is None:
            return dt.strftime("%Y-%m-%d")
        return dt.astimezone(local_tz).strftime("%Y-%m-%d")

    # Summary
    total_sessions = report.total_sessions_all_tools
    total_messages = report.total_messages_all_tools

    if all_sessions:
        all_start = min(s.start_time for s in all_sessions)
        all_end = max(s.end_time for s in all_sessions)
        date_range_start = fmt_date_local(all_start)
        date_range_end = fmt_date_local(all_end)
        days_of_history = (all_end - all_start).days + 1
    else:
        date_range_start = ""
        date_range_end = ""
        days_of_history = 0

    # Tools breakdown
    tools_summary: Dict[str, int] = {}
    for tool_key, snap in report.snapshots.items():
        label = TOOL_LABELS.get(tool_key, tool_key)
        tools_summary[label] = snap.total_sessions

    # Peak hour
    heatmap: List[List[int]] = [[0] * 24 for _ in range(7)]
    for s in all_sessions:
        for m in s.messages:
            if m.role == "user":
                local_ts = m.timestamp.astimezone(local_tz) if local_tz else m.timestamp
                dow = local_ts.weekday()
                hour = local_ts.hour
                heatmap[dow][hour] += 1

    peak_hour = 0
    peak_hour_count = 0
    for hour in range(24):
        total = sum(heatmap[dow][hour] for dow in range(7))
        if total > peak_hour_count:
            peak_hour_count = total
            peak_hour = hour
    peak_hour_label = f"{peak_hour:02d}:00\u2013{peak_hour + 1:02d}:00"

    dow_totals = [sum(heatmap[d]) for d in range(7)]
    dow_labels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    peak_day = dow_labels[dow_totals.index(max(dow_totals))] if any(dow_totals) else "N/A"

    # Avg session duration and messages per session
    if all_sessions:
        avg_dur = statistics.mean(s.duration_seconds for s in all_sessions) / 60.0
        avg_msgs = statistics.mean(s.message_count for s in all_sessions)
    else:
        avg_dur = 0.0
        avg_msgs = 0.0

    # Session characters
    char_counts: Dict[str, int] = {"autonomous": 0, "deeply_engaged": 0, "general": 0}
    for s in all_sessions:
        char_counts[s.session_character] = char_counts.get(s.session_character, 0) + 1
    total_char = max(sum(char_counts.values()), 1)
    session_characters = {
        k: {"count": v, "pct": round(v / total_char * 100)}
        for k, v in char_counts.items()
    }

    # Categories
    cat_counts: Dict[str, int] = {}
    for s in all_sessions:
        cat_counts[s.category] = cat_counts.get(s.category, 0) + 1
    total_cats = max(sum(cat_counts.values()), 1)
    categories = {
        k: {"count": v, "pct": round(v / total_cats * 100)}
        for k, v in sorted(cat_counts.items(), key=lambda x: -x[1])
    }

    # Top projects
    project_counts: Dict[str, int] = {}
    project_tool_map: Dict[str, str] = {}
    for s in all_sessions:
        if s.project_path is None:
            continue
        parts = s.project_path.replace("\\", "/").rstrip("/").split("/")
        if len(parts) >= 2:
            normalized = parts[-2] + "/" + parts[-1]
        else:
            normalized = parts[-1]
        project_counts[normalized] = project_counts.get(normalized, 0) + 1
        if normalized not in project_tool_map:
            project_tool_map[normalized] = s.tool
    top_projects = [
        {
            "path": proj,
            "sessions": cnt,
            "tool": TOOL_LABELS.get(project_tool_map.get(proj, ""), project_tool_map.get(proj, "")),
        }
        for proj, cnt in sorted(project_counts.items(), key=lambda x: -x[1])[:10]
    ]

    # Models (normalized)
    model_counts: Dict[str, int] = {}
    for s in all_sessions:
        if s.model:
            canonical = normalize_model_name(s.model)
            model_counts[canonical] = model_counts.get(canonical, 0) + 1

    # All sessions sorted by recency (across all tools), up to 6 user messages each (truncated to 300 chars)
    recent = sorted(all_sessions, key=lambda s: s.start_time, reverse=True)
    conversations = []
    for s in recent:
        user_msgs = [
            m for m in s.messages
            if m.role == "user"
            and not m.content.strip().startswith("/")
            and not _is_system_message(m.content)
        ][:6]
        msg_list = [
            {"role": "user", "content": m.content.strip()[:300]}
            for m in user_msgs
        ]
        conversations.append({
            "tool": TOOL_LABELS.get(s.tool, s.tool),
            "date": fmt_date_local(s.start_time),
            "category": s.category,
            "character": s.session_character,
            "project": s.project_path or "",
            "duration_minutes": round(s.duration_seconds / 60.0, 1),
            "message_count": s.message_count,
            "messages": msg_list,
        })

    if days_filter == 180:
        data_window = "6 months"
    elif days_filter:
        data_window = f"{days_filter} days"
    else:
        data_window = "all time"

    # Cost summary per tool
    cost_by_tool: Dict[str, Dict] = {}
    for tool_key, snap in report.snapshots.items():
        cost_sessions = [s.estimated_cost_usd for s in snap.sessions if s.estimated_cost_usd is not None]
        pru_sessions = [s.effective_prus for s in snap.sessions if s.effective_prus is not None]
        cost_by_tool[tool_key] = {
            "total_estimated_usd": round(sum(cost_sessions), 4) if cost_sessions else None,
            "total_effective_prus": round(sum(pru_sessions), 2) if pru_sessions else None,
            "has_cost_data": bool(cost_sessions),
        }

    data = {
        "summary": {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "date_range_start": date_range_start,
            "date_range_end": date_range_end,
            "days_of_history": days_of_history,
            "days_limit": days_filter,
            "data_window": data_window,
            "tools": tools_summary,
            "peak_hour": peak_hour_label,
            "peak_day": peak_day,
            "avg_session_duration_minutes": round(avg_dur, 1),
            "avg_messages_per_session": round(avg_msgs, 1),
            "peak_concurrent_sessions": report.peak_concurrent_sessions,
            "local_timezone": local_tz_name,
        },
        "session_characters": session_characters,
        "categories": categories,
        "top_projects": top_projects,
        "models": model_counts,
        "conversations": conversations,
        "cost_by_tool": cost_by_tool,
    }
    return json.dumps(data, indent=2)


def load_insights(path: str) -> dict:
    """Load AI-generated insights JSON from path. Returns dict with headline and sections."""
    try:
        with open(os.path.expanduser(path), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return {"headline": "", "sections": []}
        return data
    except Exception:
        return {"headline": "", "sections": []}


# ---------------------------------------------------------------------------
# HTML Report Renderer
# ---------------------------------------------------------------------------

TOOL_LABELS = {
    "claude_code": "Claude Code",
    "copilot_vscode": "Copilot VS Code",
    "copilot_cli": "Copilot CLI",
    "codex": "Codex",
}

ACCENT_COLORS = {
    "claude_code": "#8b5cf6",   # purple
    "copilot_vscode": "#3b82f6",  # blue
    "copilot_cli": "#10b981",   # green
    "codex": "#ef4444",        # red
}

CATEGORY_COLORS = {
    "Debugging": "#ef4444",
    "Code Generation": "#3b82f6",
    "Learning/Explanation": "#10b981",
    "Planning": "#f59e0b",
    "Writing/Docs": "#ec4899",
    "Refactoring": "#8b5cf6",
    "Setup & Config": "#06b6d4",      # cyan
    "Infrastructure": "#f97316",       # orange
    "Research & Analysis": "#a78bfa",  # light purple
    "Other": "#6b7280",
}

CHARACTER_COLORS = {
    "autonomous": "#f59e0b",
    "deeply_engaged": "#3b82f6",
    "general": "#6b7280",
}

CHARACTER_LABELS = {
    "autonomous": "Autonomous",
    "deeply_engaged": "Deeply Engaged",
    "general": "General",
}


def normalize_model_name(model: str) -> str:
    """Normalize raw model identifiers to human-readable display names.

    Handles copilot/ prefix stripping, date suffix stripping, claude-* patterns,
    GPT patterns, and o-series models.
    """
    import re as _re
    s = model.strip()

    # Strip copilot/ prefix
    if s.startswith("copilot/"):
        s = s[len("copilot/"):]

    # Normalize dot-separated versions: 4.5 → 4-5 (before other patterns)
    s = _re.sub(r'(\d+)\.(\d+)', r'\1-\2', s)

    # Strip trailing date suffix: -YYYYMMDD
    s = _re.sub(r'-\d{8}$', '', s)

    # claude-{name}-{major}-{minor}  e.g. claude-haiku-4-5, claude-sonnet-4-6
    m = _re.match(r'^claude-([a-z]+(?:-[a-z]+)*)-(\d+)-(\d+)$', s)
    if m:
        name = ' '.join(w.capitalize() for w in m.group(1).split('-'))
        return f"Claude {name} {m.group(2)}.{m.group(3)}"

    # claude-{major}-{minor}-{name}  e.g. claude-3-5-sonnet
    m = _re.match(r'^claude-(\d+)-(\d+)-([a-z]+(?:-[a-z]+)*)$', s)
    if m:
        name = ' '.join(w.capitalize() for w in m.group(3).split('-'))
        return f"Claude {m.group(1)}.{m.group(2)} {name}"

    # claude-{name}-{major}  e.g. claude-opus-4
    m = _re.match(r'^claude-([a-z]+(?:-[a-z]+)*)-(\d+)$', s)
    if m:
        name = ' '.join(w.capitalize() for w in m.group(1).split('-'))
        return f"Claude {name} {m.group(2)}"

    # claude-{name}  e.g. claude-opus
    m = _re.match(r'^claude-([a-z]+(?:-[a-z]+)*)$', s)
    if m:
        return "Claude " + ' '.join(w.capitalize() for w in m.group(1).split('-'))

    # gpt-4o, gpt-4-turbo
    m = _re.match(r'^gpt-(\S+)$', s, _re.IGNORECASE)
    if m:
        parts = m.group(1).split('-')
        return 'GPT-' + ' '.join(p.capitalize() if not p[0].isdigit() else p for p in parts)

    # o3-mini, o1-preview
    m = _re.match(r'^(o\d+)(?:-([a-z]+))?$', s, _re.IGNORECASE)
    if m:
        return f"{m.group(1)} {m.group(2).capitalize()}" if m.group(2) else m.group(1)

    return s


def _local_dt(dt: datetime, tz_info) -> datetime:
    """Convert a UTC-aware datetime to local timezone."""
    if tz_info is None:
        return dt
    return dt.astimezone(tz_info)


def render_html(report: InsightsReport, output_path: str, chartjs_src: Optional[str] = None, insights: Optional[dict] = None, days_filter: Optional[int] = None) -> None:
    """Fetch Chart.js (or use provided source) and render the full HTML report."""
    if chartjs_src is None:
        print("Fetching Chart.js from CDN ...", file=sys.stderr)
        chartjs_url = "https://cdn.jsdelivr.net/npm/chart.js"
        try:
            with urllib.request.urlopen(chartjs_url, timeout=30) as resp:
                chartjs_src = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"Failed to fetch Chart.js from {chartjs_url}\nHTTPError: {exc}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Failed to fetch Chart.js from {chartjs_url}\n{type(exc).__name__}: {exc}"
            ) from exc

    print("Generating report ...", file=sys.stderr)
    local_tz = datetime.now().astimezone().tzinfo

    def fmt_dt(dt: datetime) -> str:
        return _local_dt(dt, local_tz).strftime("%Y-%m-%d %H:%M")

    def fmt_date(dt: datetime) -> str:
        return _local_dt(dt, local_tz).strftime("%Y-%m-%d")

    all_sessions: List[Session] = []
    for snap in report.snapshots.values():
        all_sessions.extend(snap.sessions)

    # --- Compute hourly heatmap data ---
    # heatmap[day_of_week][hour] = message_count  (day 0=Mon..6=Sun)
    heatmap: List[List[int]] = [[0] * 24 for _ in range(7)]
    for s in all_sessions:
        for m in s.messages:
            if m.role == "user":
                local_ts = _local_dt(m.timestamp, local_tz)
                dow = local_ts.weekday()  # 0=Mon
                hour = local_ts.hour
                heatmap[dow][hour] += 1

    # Peak hour
    peak_hour = 0
    peak_hour_count = 0
    for hour in range(24):
        total = sum(heatmap[dow][hour] for dow in range(7))
        if total > peak_hour_count:
            peak_hour_count = total
            peak_hour = hour

    # Day of week totals
    dow_totals = [sum(heatmap[d]) for d in range(7)]
    dow_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    peak_dow = dow_labels[dow_totals.index(max(dow_totals))] if any(dow_totals) else "N/A"

    # --- Tool usage data ---
    tool_names = list(report.snapshots.keys())
    tool_labels = [TOOL_LABELS.get(t, t) for t in tool_names]
    tool_sessions = [report.snapshots[t].total_sessions for t in tool_names]
    tool_messages = [report.snapshots[t].total_messages for t in tool_names]
    tool_colors = [ACCENT_COLORS.get(t, "#6b7280") for t in tool_names]

    # --- Session character data ---
    char_counts: Dict[str, int] = {"autonomous": 0, "deeply_engaged": 0, "general": 0}
    for s in all_sessions:
        char_counts[s.session_character] = char_counts.get(s.session_character, 0) + 1

    # Per-tool character breakdown
    tool_char_data: Dict[str, Dict[str, int]] = {}
    for tool in tool_names:
        snap = report.snapshots[tool]
        tcd: Dict[str, int] = {"autonomous": 0, "deeply_engaged": 0, "general": 0}
        for s in snap.sessions:
            tcd[s.session_character] = tcd.get(s.session_character, 0) + 1
        tool_char_data[tool] = tcd

    # --- Category data ---
    cat_counts: Dict[str, int] = {}
    for s in all_sessions:
        cat_counts[s.category] = cat_counts.get(s.category, 0) + 1

    all_cats = [c[0] for c in CATEGORY_RULES if c[0] != "Other"]
    if "Other" in cat_counts:
        all_cats.append("Other")
    # Only include categories that appear
    present_cats = [c for c in all_cats if cat_counts.get(c, 0) > 0]
    cat_values = [cat_counts.get(c, 0) for c in present_cats]
    cat_colors_list = [CATEGORY_COLORS.get(c, "#6b7280") for c in present_cats]

    # --- Mode data ---
    MODE_LABELS = {
        "plan": "Plan",
        "edit": "Edit (Auto-accept)",
        "default": "Default",
        "agent": "Agent",
        "ask": "Ask",
        "autopilot": "Autopilot",
    }
    MODE_COLORS = {
        "plan": "#f59e0b",
        "edit": "#10b981",
        "default": "#6b7280",
        "agent": "#8b5cf6",
        "ask": "#3b82f6",
        "autopilot": "#ec4899",
    }
    mode_data: Dict[str, Dict[str, int]] = {}
    has_mode = False
    for tool in tool_names:
        snap = report.snapshots[tool]
        counts: Dict[str, int] = {}
        for s in snap.sessions:
            key = s.mode if s.mode is not None else "none"
            counts[key] = counts.get(key, 0) + 1
        mode_data[tool] = counts
        if any(v > 0 for k, v in counts.items() if k != "none"):
            has_mode = True

    # --- Model data ---
    model_counts: Dict[str, int] = {}
    model_variants: Dict[str, set] = {}  # canonical → set of raw names
    for s in all_sessions:
        if s.model:
            canonical = normalize_model_name(s.model)
            model_counts[canonical] = model_counts.get(canonical, 0) + 1
            model_variants.setdefault(canonical, set()).add(s.model)
    has_model = bool(model_counts)
    model_names = sorted(model_counts.keys(), key=lambda m: -model_counts[m])
    model_values = [model_counts[m] for m in model_names]

    # --- Token data ---
    total_input = sum(
        snap.total_input_tokens for snap in report.snapshots.values()
        if snap.total_input_tokens is not None
    )
    total_output = sum(
        snap.total_output_tokens for snap in report.snapshots.values()
        if snap.total_output_tokens is not None
    )
    # Check for Codex combined tokens as well
    total_codex_tokens = sum(
        sum(s.total_tokens for s in snap.sessions if s.total_tokens is not None and not s.cost_breakdown_available)
        for snap in report.snapshots.values()
    )
    has_tokens = total_input > 0 or total_output > 0 or total_codex_tokens > 0

    # --- Cost data ---
    tool_cost: Dict[str, Optional[float]] = {}
    tool_prus: Dict[str, Optional[float]] = {}
    for t in tool_names:
        sess_list = report.snapshots[t].sessions
        costs = [s.estimated_cost_usd for s in sess_list if s.estimated_cost_usd is not None]
        prus = [s.effective_prus for s in sess_list if s.effective_prus is not None]
        tool_cost[t] = round(sum(costs), 4) if costs else None
        tool_prus[t] = round(sum(prus), 2) if prus else None
    has_costs = any(v is not None for v in tool_cost.values())
    has_prus = any(v is not None for v in tool_prus.values())

    # --- Per-tool token display (accounting for Codex limitations) ---
    # Build display strings for input/output tokens per tool
    tool_input_display: Dict[str, str] = {}
    tool_output_display: Dict[str, str] = {}
    has_codex_tokens = False
    for t in tool_names:
        snap = report.snapshots[t]
        if snap.total_input_tokens is not None and snap.total_output_tokens is not None:
            # Standard case: full breakdown available
            tool_input_display[t] = f"{snap.total_input_tokens:,}"
            tool_output_display[t] = f"{snap.total_output_tokens:,}"
        else:
            # Check if this tool has any Codex sessions with total_tokens
            sess_list = snap.sessions
            codex_total = sum(s.total_tokens for s in sess_list if s.total_tokens is not None and not s.cost_breakdown_available)
            if codex_total > 0:
                # Codex only exposes a combined token total (no input/output split).
                # Show it in the input column so it isn't mistaken for output-only.
                tool_input_display[t] = f"{codex_total:,}*"
                tool_output_display[t] = "—"
                has_codex_tokens = True
            else:
                # No data available
                tool_input_display[t] = "—"
                tool_output_display[t] = "—"

    # --- Date range ---
    if all_sessions:
        all_start = min(s.start_time for s in all_sessions)
        all_end = max(s.end_time for s in all_sessions)
        date_range_str = f"{fmt_date(all_start)} → {fmt_date(all_end)}"
    else:
        date_range_str = "No data"

    # --- Window note for header ---
    if days_filter == 180:
        window_note = " &nbsp;·&nbsp; 6-month window"
    elif days_filter:
        window_note = f" &nbsp;·&nbsp; {days_filter}-day window"
    else:
        window_note = " &nbsp;·&nbsp; all-time history"

    # --- Top insights ---
    top_tool = tool_labels[tool_sessions.index(max(tool_sessions))] if tool_sessions else "N/A"
    top_cat = max(cat_counts, key=lambda c: cat_counts[c]) if cat_counts else "N/A"
    def _fmt_ampm(h: int) -> str:
        if h == 0: return "12 AM"
        if h < 12: return f"{h} AM"
        if h == 12: return "12 PM"
        return f"{h - 12} PM"

    peak_hour_label = f"{_fmt_ampm(peak_hour)}–{_fmt_ampm(peak_hour + 1)}"

    autonomous_pct = round(char_counts["autonomous"] / max(sum(char_counts.values()), 1) * 100)
    engaged_pct = round(char_counts["deeply_engaged"] / max(sum(char_counts.values()), 1) * 100)

    # --- Build cost footnote with Codex notice if applicable ---
    cost_footnote = 'ⓘ Cost figures are <em>estimated</em> at list price using locally stored price schedules. Plan allowances and actual billing may differ.<br><strong>Claude Code:</strong> (input tokens ÷ 1M × input $/M) + (output tokens ÷ 1M × output $/M) — e.g. Sonnet 4.6 at $3.00/M in · $15.00/M out, Haiku 4.5 at $0.80/M in · $4.00/M out, Opus 4.6 at $15.00/M in · $75.00/M out.<br><strong>Copilot:</strong> requests × per-model PRU multiplier = effective PRUs × $0.04/PRU — e.g. gpt-4o and most Claude models at 1.0×, Opus at 3.0×.'
    if has_codex_tokens:
        cost_footnote += '<br><strong>Codex:</strong> Token count is combined (input + output) from the Codex database — individual input/output breakdown unavailable. Combined total shown in the Input column; Output shows "—".'

    # Build HTML/CSS heatmap grid
    _heatmap_day_colors = ["#8b5cf6", "#3b82f6", "#10b981", "#f59e0b", "#ec4899", "#06b6d4", "#f97316"]
    _heatmap_day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    _hm_max = max(heatmap[d][h] for d in range(7) for h in range(24)) or 1
    _hm_hour_label_positions = {0, 6, 12, 18, 23}

    def _build_heatmap_html() -> str:
        lines = ['<div class="heatmap-grid-wrap">']
        # Hour labels row
        lines.append('<div class="heatmap-hour-labels">')
        lines.append('<span class="heatmap-day-label"></span>')  # spacer for day label column
        for h in range(24):
            if h in _hm_hour_label_positions:
                lines.append(f'<span class="heatmap-hour-tick">{_fmt_ampm(h)}</span>')
            else:
                lines.append('<span class="heatmap-hour-tick heatmap-hour-tick-hidden"></span>')
        lines.append('</div>')
        # Day rows
        for d in range(7):
            color = _heatmap_day_colors[d]
            lines.append('<div class="heatmap-row">')
            lines.append(f'<span class="heatmap-day-label">{_heatmap_day_labels[d]}</span>')
            for h in range(24):
                count = heatmap[d][h]
                opacity = count / _hm_max * (1.0 - 0.05) + 0.05
                tooltip = f"{_heatmap_day_labels[d]} {_fmt_ampm(h)} \u2014 {count} messages"
                lines.append(
                    f'<div class="heatmap-cell" title="{tooltip}" '
                    f'style="background:{color};opacity:{opacity:.3f}"></div>'
                )
            lines.append('</div>')
        lines.append('</div>')
        return "\n".join(lines)

    heatmap_grid_html = _build_heatmap_html()


    # Per-tool char stacked
    char_stacked_datasets = []
    for char_key, char_label in CHARACTER_LABELS.items():
        char_stacked_datasets.append({
            "label": char_label,
            "data": [tool_char_data.get(t, {}).get(char_key, 0) for t in tool_names],
            "backgroundColor": CHARACTER_COLORS[char_key],
        })

    def js_list(lst) -> str:
        return json.dumps(lst)

    def _html_escape(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    def _md_inline_to_html(text: str) -> str:
        """Convert inline markdown to HTML: **bold**, `code`, [link](url). Escapes all other text."""
        import re as _re
        pattern = _re.compile(r'\[([^\]]+)\]\(([^)]+)\)|\*\*(.+?)\*\*|`([^`]+)`')
        result = []
        last = 0
        for m in pattern.finditer(text):
            result.append(_html_escape(text[last:m.start()]))
            if m.group(1) is not None:
                result.append(f'<a href="{_html_escape(m.group(2))}" target="_blank" rel="noopener">{_html_escape(m.group(1))}</a>')
            elif m.group(3) is not None:
                result.append(f'<strong>{_html_escape(m.group(3))}</strong>')
            else:
                result.append(f'<code>{_html_escape(m.group(4))}</code>')
            last = m.end()
        result.append(_html_escape(text[last:]))
        return "".join(result)

    def js_obj(obj) -> str:
        return json.dumps(obj)

    # Mode chart data (doughnut per tool)
    mode_charts_html = ""
    if has_mode:
        for tool in tool_names:
            md = mode_data[tool]
            present = {k: v for k, v in md.items() if k != "none" and v > 0}
            if not present:
                continue
            tl = TOOL_LABELS.get(tool, tool)
            chart_id = f"modeChart_{tool}"
            mode_charts_html += f"""
        <div class="chart-card">
          <h3 class="chart-title">{tl}</h3>
          <div class="chart-wrap chart-wrap-sm">
            <canvas id="{chart_id}"></canvas>
          </div>
        </div>"""

    # Model bar chart
    model_chart_html = ""
    if has_model:
        # Build variant footnote for grouped models
        grouped = [(name, sorted(variants)) for name, variants in model_variants.items() if len(variants) > 1]
        if grouped:
            grouped_sorted = sorted(grouped, key=lambda x: -model_counts[x[0]])
            variant_parts = [f"{name} ({', '.join(raw_list)})" for name, raw_list in grouped_sorted]
            variant_footnote = (
                f'<div style="margin-top:12px;font-size:0.78rem;color:var(--text-muted);line-height:1.6">'
                f'<strong style="color:var(--text-muted)">Grouped variants:</strong> '
                + " &nbsp;·&nbsp; ".join(f'<em>{_html_escape(p)}</em>' for p in variant_parts)
                + "</div>"
            )
        else:
            variant_footnote = ""
        model_chart_html = f"""
      <div class="chart-card chart-card-wide">
        <h3 class="chart-title">Model Usage (sessions)</h3>
        <div class="chart-wrap">
          <canvas id="modelChart"></canvas>
        </div>
        {variant_footnote}
      </div>"""

    # Token + PRU summary
    token_html = ""
    if has_tokens or has_prus:
        total_prus_all = sum(v for v in tool_prus.values() if v is not None)
        pru_stat = f"""
        <div class="stat-item">
          <div class="stat-value">{total_prus_all:.1f}</div>
          <div class="stat-label">Total PRUs</div>
        </div>""" if has_prus else ""
        token_stats = f"""
        <div class="stat-item">
          <div class="stat-value">{total_input:,}</div>
          <div class="stat-label">Input Tokens</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{total_output:,}</div>
          <div class="stat-label">Output Tokens</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{(total_input + total_output):,}</div>
          <div class="stat-label">Total Tokens</div>
        </div>""" if has_tokens else ""
        token_html = f"""
      <div class="stat-row">{token_stats}{pru_stat}
      </div>"""

    gen_ts_local = fmt_dt(report.generated_at)

    # --- Build AI Insights section HTML ---
    if insights is None:
        insights = {}
    ins_headline = insights.get("headline", "")
    ins_sections = insights.get("sections", [])
    ins_at_a_glance = insights.get("at_a_glance", {})
    ins_work_themes = insights.get("work_themes", [])
    has_work_themes = bool(ins_work_themes)

    if ins_headline or ins_sections or ins_at_a_glance or has_work_themes:
        # Headline
        headline_html = ""
        if ins_headline:
            headline_html = f'<div class="insight-headline"><div class="insight-headline-text">{_html_escape(ins_headline)}</div></div>'

        # Work Themes grid
        work_themes_html = ""
        if has_work_themes:
            theme_cards = ""
            for theme in ins_work_themes:
                tname = _html_escape(str(theme.get("name", "")))
                tdesc = _html_escape(str(theme.get("description", "")))
                tcount = theme.get("session_count")
                tcount_html = f'<div class="work-theme-count">{int(tcount)} sessions</div>' if tcount else ""
                theme_cards += f"""<div class="work-theme-card">
  <div class="work-theme-name">{tname}</div>
  <div class="work-theme-desc">{tdesc}</div>
  {tcount_html}
</div>
"""
            work_themes_html = f"""
<div class="work-themes-section">
  <div class="work-themes-label">Work Themes</div>
  <div class="work-themes-grid">{theme_cards}</div>
</div>"""

        def _glance_body(text: str) -> str:
            """Render glance text: split into bullets if multiple sentences, else plain <p>."""
            import re as _re
            sentences = [s.strip() for s in _re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]
            if len(sentences) > 1:
                items = "".join(f"<li>{_html_escape(s)}</li>" for s in sentences)
                return f'<ul class="insight-bullets insight-bullets-sm">{items}</ul>'
            return f"<p>{_html_escape(text)}</p>"

        # At a Glance card
        glance_html = ""
        if ins_at_a_glance:
            working_body = _glance_body(ins_at_a_glance.get("whats_working", ""))
            hindering_body = _glance_body(ins_at_a_glance.get("whats_hindering", ""))
            glance_html = f"""
<div class="insight-glance">
  <div class="insight-glance-col insight-glance-working">
    <div class="insight-glance-label">✦ What&#39;s Working</div>
    {working_body}
  </div>
  <div class="insight-glance-col insight-glance-hindering">
    <div class="insight-glance-label">⚠ What&#39;s Hindering</div>
    {hindering_body}
  </div>
</div>"""

        # Section cards — "How to Go More Autonomous" gets special treatment
        cards_html = ""
        for sec in ins_sections:
            title = _html_escape(sec.get("title", ""))
            extra_class = " insight-card-autonomous" if "Autonomous" in sec.get("title", "") else ""
            if "bullets" in sec and isinstance(sec["bullets"], list):
                items_html = "".join(
                    f"<li>{_md_inline_to_html(b)}</li>" for b in sec["bullets"]
                )
                body_html = f'<ul class="insight-bullets">{items_html}</ul>'
            else:
                body_html = f'<p>{_html_escape(sec.get("body", ""))}</p>'
            cards_html += f'<div class="insight-card{extra_class}"><h3>{title}</h3>{body_html}</div>\n'

        grid_html = f'<div class="insight-grid">{cards_html}</div>' if cards_html else ""
        insights_body_html = f"""{headline_html}{work_themes_html}{glance_html}{grid_html}"""
    else:
        has_work_themes = False
        insights_body_html = '<div class="insight-placeholder">Generate insights by running the skill and asking: &#8220;generate my AI usage report with insights&#8221;</div>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>My AI Usage Insights</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface2: #222535;
    --border: #2d3148;
    --text: #e2e8f0;
    --text-muted: #94a3b8;
    --purple: #8b5cf6;
    --blue: #3b82f6;
    --green: #10b981;
    --amber: #f59e0b;
    --pink: #ec4899;
    --red: #ef4444;
    --radius: 12px;
    --shadow: 0 4px 24px rgba(0,0,0,0.4);
  }}

  body {{
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
  }}

  .container {{ max-width: 1200px; margin: 0 auto; padding: 0 24px; }}

  /* Header */
  .header {{
    background: linear-gradient(135deg, #0f1117 0%, #1a1d27 50%, #1e1530 100%);
    border-bottom: 1px solid var(--border);
    padding: 40px 0 32px;
  }}
  .header-inner {{ display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 16px; }}
  .header-title {{ font-size: 2rem; font-weight: 700; background: linear-gradient(135deg, var(--purple), var(--blue)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }}
  .header-subtitle {{ color: var(--text-muted); font-size: 0.9rem; margin-top: 4px; }}
  .header-meta {{ text-align: right; }}
  .header-meta .tz {{ font-size: 0.85rem; color: var(--text-muted); }}
  .header-meta .gen-time {{ font-size: 0.8rem; color: var(--text-muted); margin-top: 4px; }}

  /* Nav */
  .nav {{
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 100;
  }}
  .nav-inner {{ display: flex; gap: 0; overflow-x: auto; }}
  .nav-link {{ padding: 12px 18px; color: var(--text-muted); text-decoration: none; font-size: 0.85rem; font-weight: 500; white-space: nowrap; border-bottom: 2px solid transparent; transition: all 0.15s; }}
  .nav-link:hover {{ color: var(--text); border-bottom-color: var(--purple); }}

  /* Main content */
  .main {{ padding: 40px 0 80px; }}

  /* Sections */
  .section {{ margin-bottom: 60px; }}
  .section-header {{ margin-bottom: 24px; }}
  .section-title {{ font-size: 1.4rem; font-weight: 600; color: var(--text); }}
  .section-desc {{ color: var(--text-muted); font-size: 0.9rem; margin-top: 4px; }}

  /* Cards */
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    box-shadow: var(--shadow);
  }}
  .card + .card {{ margin-top: 16px; }}

  /* Stat cards row */
  .stat-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 24px; }}
  .stat-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    text-align: center;
    box-shadow: var(--shadow);
    transition: transform 0.15s;
  }}
  .stat-card:hover {{ transform: translateY(-2px); }}
  .stat-card .value {{ font-size: 2rem; font-weight: 700; line-height: 1; }}
  .stat-card .label {{ font-size: 0.8rem; color: var(--text-muted); margin-top: 6px; text-transform: uppercase; letter-spacing: 0.05em; }}

  /* Insight callout */
  .insight-callout {{
    background: linear-gradient(135deg, rgba(139,92,246,0.1), rgba(59,130,246,0.1));
    border: 1px solid rgba(139,92,246,0.3);
    border-radius: var(--radius);
    padding: 16px 20px;
    font-size: 0.9rem;
    color: var(--text);
    margin-top: 16px;
  }}
  .insight-callout strong {{ color: var(--purple); }}

  /* Chart grid */
  .chart-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
  .chart-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    box-shadow: var(--shadow);
  }}
  .chart-card-wide {{ grid-column: 1 / -1; }}
  .chart-title {{ font-size: 1rem; font-weight: 600; margin-bottom: 16px; color: var(--text); }}
  .chart-wrap {{ position: relative; width: 100%; height: 240px; }}
  .chart-wrap-sm {{ height: 180px; }}
  .chart-wrap-tall {{ height: 320px; }}
  .chart-wrap-heatmap {{ height: 280px; }}

  /* Table */
  .data-table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
  .data-table th {{ text-align: left; padding: 10px 14px; color: var(--text-muted); font-weight: 500; border-bottom: 1px solid var(--border); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; }}
  .data-table td {{ padding: 10px 14px; border-bottom: 1px solid rgba(45,49,72,0.5); }}
  .data-table tr:last-child td {{ border-bottom: none; }}
  .data-table tr:hover td {{ background: rgba(255,255,255,0.02); }}

  .badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 500;
  }}

  /* Stat row (inline) */
  .stat-row {{ display: flex; gap: 24px; flex-wrap: wrap; margin-top: 16px; }}
  .stat-item .stat-value {{ font-size: 1.5rem; font-weight: 700; }}
  .stat-item .stat-label {{ font-size: 0.8rem; color: var(--text-muted); }}

  /* Character legend */
  .char-legend {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 16px; }}
  .char-dot {{ display: flex; align-items: center; gap: 6px; font-size: 0.85rem; }}
  .char-dot::before {{ content: ''; display: inline-block; width: 10px; height: 10px; border-radius: 50%; }}

  /* Footer */
  .footer {{ background: var(--surface); border-top: 1px solid var(--border); padding: 32px 0; margin-top: 40px; }}
  .footer-content {{ display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 20px; }}
  .footer-sources {{ font-size: 0.8rem; color: var(--text-muted); }}
  .footer-sources ul {{ list-style: none; margin-top: 6px; }}
  .footer-sources li {{ padding: 2px 0; }}
  .footer-brand {{ font-size: 0.8rem; color: var(--text-muted); text-align: right; }}

  /* No data */
  .no-data {{ text-align: center; padding: 60px; color: var(--text-muted); }}
  .no-data-icon {{ font-size: 3rem; margin-bottom: 16px; }}

  /* Work Themes */
  .work-themes-section {{
    margin-bottom: 28px;
  }}
  .work-themes-label {{
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--purple);
    margin-bottom: 12px;
  }}
  .work-themes-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 14px;
  }}
  .work-theme-card {{
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px;
  }}
  .work-theme-name {{
    font-weight: 600;
    color: var(--purple);
    font-size: 0.9rem;
    margin-bottom: 6px;
  }}
  .work-theme-desc {{
    color: var(--text-muted);
    font-size: 0.85rem;
    line-height: 1.5;
    margin-bottom: 8px;
  }}
  .work-theme-count {{
    font-size: 0.8rem;
    color: var(--amber);
    font-weight: 500;
  }}

  /* AI Insights */
  .insight-headline {{
    background: linear-gradient(135deg, rgba(139,92,246,0.12), rgba(99,102,241,0.08));
    border: 1px solid rgba(139,92,246,0.35);
    border-radius: var(--radius);
    padding: 28px 32px;
    margin-bottom: 28px;
    font-size: 1.25rem;
    font-style: italic;
    line-height: 1.65;
    color: var(--text);
    position: relative;
  }}
  .insight-headline::before {{
    content: '\201C';
    font-size: 3rem;
    color: rgba(139,92,246,0.4);
    line-height: 1;
    position: absolute;
    top: 12px;
    left: 16px;
    font-style: normal;
  }}
  .insight-headline-text {{
    padding-left: 28px;
  }}

  .insight-grid {{
    display: grid;
    grid-template-columns: 1fr;
    gap: 20px;
  }}

  .insight-glance {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 20px;
  }}
  @media (max-width: 600px) {{
    .insight-glance {{ grid-template-columns: 1fr; }}
  }}
  .insight-glance-col {{
    border-radius: var(--radius);
    padding: 18px 20px;
  }}
  .insight-glance-working {{
    background: rgba(16, 185, 129, 0.08);
    border: 1px solid rgba(16, 185, 129, 0.25);
  }}
  .insight-glance-hindering {{
    background: rgba(245, 158, 11, 0.08);
    border: 1px solid rgba(245, 158, 11, 0.25);
  }}
  .insight-glance-label {{
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 8px;
  }}
  .insight-glance-working .insight-glance-label {{ color: #10b981; }}
  .insight-glance-hindering .insight-glance-label {{ color: #f59e0b; }}
  .insight-glance-col p {{
    font-size: 0.9rem;
    line-height: 1.6;
    color: var(--text);
  }}

  .insight-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 22px 24px;
    box-shadow: var(--shadow);
  }}
  .insight-card-autonomous {{
    grid-column: 1 / -1;
    border-color: rgba(139, 92, 246, 0.4);
    background: rgba(139, 92, 246, 0.05);
  }}
  .insight-card-autonomous h3 {{
    color: #a78bfa !important;
  }}
  .insight-card h3 {{
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--purple);
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  .insight-card p {{
    color: var(--text);
    font-size: 0.92rem;
    line-height: 1.65;
  }}

  .insight-bullets {{
    list-style: none;
    padding: 0;
    margin: 0;
    color: var(--text);
    font-size: 0.92rem;
    line-height: 1.6;
  }}
  .insight-bullets li {{
    padding: 3px 0 3px 16px;
    position: relative;
  }}
  .insight-bullets li::before {{
    content: '•';
    position: absolute;
    left: 0;
    color: var(--purple);
  }}
  .insight-bullets-sm {{
    font-size: 0.9rem;
  }}
  .insight-glance-col .insight-bullets li {{
    font-size: 0.9rem;
  }}

  .insight-placeholder {{
    background: var(--surface);
    border: 1px dashed var(--border);
    border-radius: var(--radius);
    padding: 32px;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.9rem;
    line-height: 1.6;
  }}
  .insight-placeholder code {{
    background: rgba(139,92,246,0.12);
    color: var(--purple);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.85rem;
  }}

  /* Heatmap grid */
  .heatmap-grid-wrap {{
    padding-bottom: 4px;
    margin-top: 12px;
    width: 100%;
  }}
  .heatmap-hour-labels {{
    display: flex;
    align-items: center;
    gap: 3px;
    margin-bottom: 3px;
  }}
  .heatmap-hour-tick {{
    flex: 1;
    text-align: center;
    font-size: 0.68rem;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
  }}
  .heatmap-hour-tick-hidden {{
    visibility: hidden;
  }}
  .heatmap-row {{
    display: flex;
    align-items: center;
    gap: 3px;
    margin-bottom: 3px;
  }}
  .heatmap-day-label {{
    width: 28px;
    font-size: 0.72rem;
    color: var(--text-muted);
    flex-shrink: 0;
    text-align: right;
    padding-right: 4px;
  }}
  .heatmap-cell {{
    flex: 1;
    aspect-ratio: 1;
    border-radius: 4px;
    cursor: default;
    transition: transform 0.1s;
    min-width: 0;
  }}
  .heatmap-cell:hover {{
    transform: scale(1.15);
    z-index: 1;
    position: relative;
  }}

  /* Responsive */
  @media (max-width: 600px) {{
    .header-inner {{ flex-direction: column; }}
    .header-meta {{ text-align: left; }}
    .stat-cards {{ grid-template-columns: repeat(2, 1fr); }}
    .nav-link {{ padding: 12px 12px; font-size: 0.8rem; }}
  }}
</style>
</head>
<body>

<!-- HEADER -->
<header class="header">
  <div class="container">
    <div class="header-inner">
      <div>
        <div class="header-title">My AI Usage Insights</div>
        <div class="header-subtitle">Personal analytics across all your AI tools &nbsp;·&nbsp; {date_range_str}{window_note}</div>
      </div>
      <div class="header-meta">
        <div class="tz">Timezone: {report.local_timezone}</div>
        <div class="gen-time">Generated: {gen_ts_local}</div>
      </div>
    </div>
  </div>
</header>

<!-- NAV -->
<nav class="nav">
  <div class="container">
    <div class="nav-inner">
      <a class="nav-link" href="#summary">Summary</a>
      <a class="nav-link" href="#tool-split">Tool Split</a>
      <a class="nav-link" href="#patterns">Patterns</a>
      <a class="nav-link" href="#character">Session Character</a>
      <a class="nav-link" href="#insights">AI Insights</a>
      {'<a class="nav-link" href="#categories">Categories</a>' if not has_work_themes else ''}
      {'<a class="nav-link" href="#mode-model">Mode & Model</a>' if has_mode or has_model else ''}
    </div>
  </div>
</nav>

<main class="main">
<div class="container">

<!-- SECTION: SUMMARY -->
<section class="section" id="summary">
  <div class="section-header">
    <div class="section-title">Headline Summary</div>
    <div class="section-desc">Your AI usage at a glance</div>
  </div>

  <div class="stat-cards">
    <div class="stat-card">
      <div class="value" style="color: var(--purple)">{report.total_sessions_all_tools}</div>
      <div class="label">Total Sessions</div>
    </div>
    <div class="stat-card">
      <div class="value" style="color: var(--blue)">{report.total_messages_all_tools}</div>
      <div class="label">Total Messages</div>
    </div>
    <div class="stat-card">
      <div class="value" style="color: var(--amber)">{report.peak_concurrent_sessions}</div>
      <div class="label">Peak Concurrent</div>
    </div>
    <div class="stat-card">
      <div class="value" style="color: var(--green)">{report.avg_concurrent_sessions:.1f}</div>
      <div class="label">Avg Concurrent</div>
    </div>
    <div class="stat-card">
      <div class="value" style="color: var(--pink)">{len(report.snapshots)}</div>
      <div class="label">Tools Used</div>
    </div>
    {f"""<div class="stat-card" title="Estimated at list price using locally stored price schedules">
      <div class="value" style="color: var(--green)">${sum(v for v in tool_cost.values() if v is not None):.2f}</div>
      <div class="label">Est. Total Cost ⓘ</div>
    </div>""" if has_costs else ""}
  </div>

  <div class="insight-callout">
    <strong>Top Insights</strong><br>
    · Your most-used tool is <strong>{top_tool}</strong> by session count.<br>
    · Your peak activity hour is <strong>{peak_hour_label}</strong>.<br>
    · Most sessions are categorized as <strong>{top_cat}</strong>.<br>
    · <strong>{autonomous_pct}%</strong> of sessions are autonomous, <strong>{engaged_pct}%</strong> deeply engaged.
  </div>
</section>

<!-- SECTION: TOOL SPLIT -->
<section class="section" id="tool-split">
  <div class="section-header">
    <div class="section-title">Tool Usage Split</div>
    <div class="section-desc">Session count and message volume per AI tool</div>
  </div>

  <div class="chart-grid">
    <div class="chart-card">
      <h3 class="chart-title">Sessions by Tool</h3>
      <div class="chart-wrap">
        <canvas id="toolDoughnut"></canvas>
      </div>
    </div>
    <div class="chart-card">
      <h3 class="chart-title">Messages by Tool</h3>
      <div class="chart-wrap">
        <canvas id="toolMessages"></canvas>
      </div>
    </div>
    <div class="chart-card chart-card-wide">
      <h3 class="chart-title">Per-Tool Statistics</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th>Tool</th>
            <th>Sessions</th>
            <th>Messages</th>
            <th>Session %</th>
            <th>Date Range</th>
            {'<th>Input Tokens</th><th>Output Tokens</th>' if has_tokens else ''}
            {'<th>Effective PRUs</th>' if has_prus else ''}
            {'<th title="Claude Code: (input tokens ÷ 1M × $/M) + (output tokens ÷ 1M × $/M). Copilot: requests × PRU multiplier × $0.04/PRU. Estimated at list price; plan allowances may differ.">Est. Cost (USD) ⓘ</th>' if has_costs else ''}
          </tr>
        </thead>
        <tbody>
          {"".join(f"""
          <tr>
            <td><span class="badge" style="background:rgba({','.join(str(int(ACCENT_COLORS.get(t,'#6b7280').lstrip('#')[i:i+2],16)) for i in (0,2,4))},0.2);color:{ACCENT_COLORS.get(t,'#6b7280')}">{TOOL_LABELS.get(t,t)}</span></td>
            <td>{report.snapshots[t].total_sessions}</td>
            <td>{report.snapshots[t].total_messages}</td>
            <td>{round(report.snapshots[t].total_sessions / max(report.total_sessions_all_tools, 1) * 100)}%</td>
            <td style="color:var(--text-muted);font-size:0.8rem">{fmt_date(report.snapshots[t].date_range_start)} → {fmt_date(report.snapshots[t].date_range_end)}</td>
            {'<td>' + tool_input_display[t] + '</td><td>' + tool_output_display[t] + '</td>' if has_tokens else ''}
            {''.join([f'<td>' + (f"{tool_prus[t]:.1f}" if tool_prus[t] is not None else "N/A") + '</td>']) if has_prus else ''}
            {''.join([f'<td title="Estimated at list price; plan allowances may reduce actual cost">' + (f"${tool_cost[t]:.4f}" if tool_cost[t] is not None else "N/A") + '</td>']) if has_costs else ''}
          </tr>""" for t in tool_names)}
        </tbody>
      </table>
      {'<p style="font-size:0.75rem;color:var(--text-muted);margin-top:8px">' + cost_footnote + '</p>' if has_costs else ''}
      {token_html}
    </div>
  </div>
</section>

<!-- SECTION: PATTERNS -->
<section class="section" id="patterns">
  <div class="section-header">
    <div class="section-title">Usage Patterns</div>
    <div class="section-desc">When you use AI tools — by hour of day and day of week</div>
  </div>

  <div class="chart-grid">
    <div class="chart-card chart-card-wide">
      <h3 class="chart-title">Hourly Activity Heatmap (messages per hour)</h3>
      {heatmap_grid_html}
      <div style="margin-top:12px;font-size:0.8rem;color:var(--text-muted)">
        Peak hour: <strong style="color:var(--amber)">{peak_hour_label}</strong> with {peak_hour_count} messages
      </div>
    </div>
    <div class="chart-card chart-card-wide">
      <h3 class="chart-title">Activity by Day of Week</h3>
      <div class="chart-wrap">
        <canvas id="dowChart"></canvas>
      </div>
      <div style="margin-top:12px;font-size:0.8rem;color:var(--text-muted)">
        Most active day: <strong style="color:var(--blue)">{peak_dow}</strong>
      </div>
    </div>
    <div class="chart-card chart-card-wide">
      <h3 class="chart-title">Hourly Distribution (all days combined)</h3>
      <div class="chart-wrap">
        <canvas id="hourlyBar"></canvas>
      </div>
    </div>
  </div>
</section>

<!-- SECTION: SESSION CHARACTER -->
<section class="section" id="character">
  <div class="section-header">
    <div class="section-title">Session Character</div>
    <div class="section-desc">How you work with AI — autonomous, deeply engaged, or general</div>
  </div>

  <div class="chart-grid">
    <div class="chart-card">
      <h3 class="chart-title">Character Distribution</h3>
      <div class="chart-wrap">
        <canvas id="charDoughnut"></canvas>
      </div>
    </div>
    <div class="chart-card">
      <h3 class="chart-title">By Tool</h3>
      <div class="chart-wrap chart-wrap-tall">
        <canvas id="charStackedBar"></canvas>
      </div>
    </div>
    <div class="chart-card chart-card-wide">
      <h3 class="chart-title">Character Definitions</h3>
      <table class="data-table">
        <thead>
          <tr><th>Character</th><th>Criteria</th><th>Sessions</th><th>%</th></tr>
        </thead>
        <tbody>
          <tr>
            <td><span class="badge" style="background:rgba(245,158,11,0.15);color:#f59e0b">Autonomous</span></td>
            <td style="color:var(--text-muted);font-size:0.82rem">≥3 tool calls per message AND duration ≥5 min — agent was churning work</td>
            <td>{char_counts['autonomous']}</td>
            <td>{round(char_counts['autonomous'] / max(sum(char_counts.values()), 1) * 100)}%</td>
          </tr>
          <tr>
            <td><span class="badge" style="background:rgba(59,130,246,0.15);color:#3b82f6">Deeply Engaged</span></td>
            <td style="color:var(--text-muted);font-size:0.82rem">≥5 messages, median gap &lt;2 min, &lt;1 tool call/message — active back-and-forth</td>
            <td>{char_counts['deeply_engaged']}</td>
            <td>{round(char_counts['deeply_engaged'] / max(sum(char_counts.values()), 1) * 100)}%</td>
          </tr>
          <tr>
            <td><span class="badge" style="background:rgba(107,114,128,0.15);color:#9ca3af">General</span></td>
            <td style="color:var(--text-muted);font-size:0.82rem">Everything else — mixed or short sessions</td>
            <td>{char_counts['general']}</td>
            <td>{round(char_counts['general'] / max(sum(char_counts.values()), 1) * 100)}%</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</section>

<!-- SECTION: AI INSIGHTS -->
<section class="section" id="insights">
  <div class="section-header">
    <div class="section-title">AI Insights</div>
    <div class="section-desc">AI-generated narrative observations about your AI usage habits</div>
  </div>
  {insights_body_html}
</section>

{"" if has_work_themes else f"""<!-- SECTION: CATEGORIES -->
<section class="section" id="categories">
  <div class="section-header">
    <div class="section-title">Conversation Categories</div>
    <div class="section-desc">Keyword-based breakdown of what you use AI for</div>
  </div>
  <div class="chart-grid">
    <div class="chart-card chart-card-wide">
      <h3 class="chart-title">Category Breakdown (sorted by frequency)</h3>
      <div class="chart-wrap chart-wrap-tall">
        <canvas id="catHorizBar"></canvas>
      </div>
    </div>
  </div>
</section>"""}

<!-- SECTION: MODE & MODEL -->
{"" if not has_mode and not has_model else f"""
<section class="section" id="mode-model">
  <div class="section-header">
    <div class="section-title">Mode &amp; Model</div>
    <div class="section-desc">Session mode and model breakdown</div>
  </div>

  <div class="chart-grid">
    {mode_charts_html if has_mode else ""}
    {model_chart_html if has_model else ""}
  </div>


</section>
"""}

</div>
</main>

<!-- FOOTER -->
<footer class="footer">
  <div class="container">
    <div class="footer-content">
      <div class="footer-sources">
        <strong>Data sources scanned:</strong>
        <ul>
          {"".join(f"<li>· {TOOL_LABELS.get(t,t)}: {report.snapshots[t].total_sessions} sessions</li>" for t in tool_names)}
        </ul>
      </div>
      <div class="footer-brand">
        Generated by <strong>myusage-skill</strong><br>
        <span style="color:var(--text-muted)">{gen_ts_local} · {report.local_timezone}</span>
      </div>
    </div>
  </div>
</footer>

<script>
// Chart.js inlined
{chartjs_src}
</script>
<script>
// ── Chart.js dark defaults ──────────────────────────────────────────────────
Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = '#2d3148';
Chart.defaults.font.family = "Inter, system-ui, sans-serif";

const PURPLE = '#8b5cf6', BLUE = '#3b82f6', GREEN = '#10b981',
      AMBER = '#f59e0b', PINK = '#ec4899', RED = '#ef4444';
const GREY = '#6b7280';
const TOOL_COLORS = {js_obj(dict(zip(tool_names, tool_colors)))};
const DOW = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
const HOURS = [
  '12 AM','1 AM','2 AM','3 AM','4 AM','5 AM','6 AM','7 AM','8 AM','9 AM','10 AM','11 AM',
  '12 PM','1 PM','2 PM','3 PM','4 PM','5 PM','6 PM','7 PM','8 PM','9 PM','10 PM','11 PM'
];

// ── Tool Doughnut ────────────────────────────────────────────────────────────
new Chart(document.getElementById('toolDoughnut'), {{
  type: 'doughnut',
  data: {{
    labels: {js_list(tool_labels)},
    datasets: [{{ data: {js_list(tool_sessions)}, backgroundColor: {js_list(tool_colors)}, borderWidth: 2, borderColor: '#1a1d27', hoverOffset: 8 }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ position: 'bottom', labels: {{ padding: 16, usePointStyle: true }} }}, tooltip: {{ callbacks: {{ label: ctx => ` ${{ctx.label}}: ${{ctx.parsed}} sessions` }} }} }}
  }}
}});

// ── Tool Messages Bar ────────────────────────────────────────────────────────
new Chart(document.getElementById('toolMessages'), {{
  type: 'bar',
  data: {{
    labels: {js_list(tool_labels)},
    datasets: [{{ label: 'Messages', data: {js_list(tool_messages)}, backgroundColor: {js_list(tool_colors)}, borderRadius: 6, borderSkipped: false }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ y: {{ grid: {{ color: '#2d3148' }}, ticks: {{ color: '#94a3b8' }} }}, x: {{ grid: {{ display: false }}, ticks: {{ color: '#94a3b8' }} }} }}
  }}
}});

// ── Heatmap — rendered as HTML/CSS grid (no Chart.js needed) ─────────────────

// ── Day of Week ──────────────────────────────────────────────────────────────
new Chart(document.getElementById('dowChart'), {{
  type: 'bar',
  data: {{
    labels: DOW,
    datasets: [{{
      label: 'Messages',
      data: {js_list(dow_totals)},
      backgroundColor: {js_list(dow_totals)}.map((v, i) => i === {dow_totals.index(max(dow_totals)) if any(dow_totals) else 0} ? AMBER : BLUE),
      borderRadius: 6,
      borderSkipped: false,
    }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ y: {{ grid: {{ color: '#2d3148' }} }}, x: {{ grid: {{ display: false }} }} }}
  }}
}});

// ── Hourly Bar (all days) ────────────────────────────────────────────────────
(function() {{
  const hd = {js_list([heatmap[d] for d in range(7)])};
  const combined = HOURS.map((_,h) => hd.reduce((s,d) => s+d[h], 0));
  new Chart(document.getElementById('hourlyBar'), {{
    type: 'bar',
    data: {{
      labels: HOURS,
      datasets: [{{ label: 'Messages', data: combined, backgroundColor: combined.map((v,i) => i==={peak_hour} ? AMBER : 'rgba(139,92,246,0.6)'), borderRadius: 4, borderSkipped: false }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ grid: {{ display: false }}, ticks: {{ color: '#94a3b8', font: {{ size: 10 }}, maxRotation: 45 }} }},
        y: {{ grid: {{ color: '#2d3148' }} }}
      }}
    }}
  }});
}})();

// ── Session Character Doughnut ───────────────────────────────────────────────
new Chart(document.getElementById('charDoughnut'), {{
  type: 'doughnut',
  data: {{
    labels: ['Autonomous', 'Deeply Engaged', 'General'],
    datasets: [{{ data: [{char_counts['autonomous']}, {char_counts['deeply_engaged']}, {char_counts['general']}], backgroundColor: [AMBER, BLUE, GREY], borderWidth: 2, borderColor: '#1a1d27', hoverOffset: 6 }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ position: 'bottom', labels: {{ padding: 16, usePointStyle: true }} }} }}
  }}
}});

// ── Session Character Stacked Bar ────────────────────────────────────────────
new Chart(document.getElementById('charStackedBar'), {{
  type: 'bar',
  data: {{
    labels: {js_list(tool_labels)},
    datasets: {js_obj(char_stacked_datasets)}
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ position: 'bottom', labels: {{ padding: 12, usePointStyle: true }} }} }},
    scales: {{
      x: {{ stacked: true, grid: {{ display: false }} }},
      y: {{ stacked: true, grid: {{ color: '#2d3148' }} }}
    }}
  }}
}});

// ── Category Horizontal Bar ──────────────────────────────────────────────────
new Chart(document.getElementById('catHorizBar'), {{
  type: 'bar',
  data: {{
    labels: {js_list(present_cats)},
    datasets: [{{ label: 'Sessions', data: {js_list(cat_values)}, backgroundColor: {js_list(cat_colors_list)}, borderRadius: 6, borderSkipped: false }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ grid: {{ color: '#2d3148' }} }},
      y: {{ grid: {{ display: false }} }}
    }}
  }}
}});

// ── Mode Charts ──────────────────────────────────────────────────────────────
{_render_mode_charts_js(tool_names, mode_data, has_mode, MODE_LABELS, MODE_COLORS)}

// ── Model Chart ──────────────────────────────────────────────────────────────
{f"""
new Chart(document.getElementById('modelChart'), {{
  type: 'bar',
  data: {{
    labels: {js_list(model_names)},
    datasets: [{{ label: 'Sessions', data: {js_list(model_values)}, backgroundColor: [PURPLE, BLUE, GREEN, AMBER, PINK, RED, GREY].slice(0, {len(model_names)}), borderRadius: 6, borderSkipped: false }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ grid: {{ display: false }}, ticks: {{ maxRotation: 30 }} }},
      y: {{ grid: {{ color: '#2d3148' }} }}
    }}
  }}
}});
""" if has_model else "// No model data"}

</script>
</body>
</html>"""

    output_path = os.path.expanduser(output_path)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html)


def _render_mode_charts_js(
    tool_names: List[str],
    mode_data: Dict[str, Dict[str, int]],
    has_mode: bool,
    mode_labels: Optional[Dict[str, str]] = None,
    mode_colors: Optional[Dict[str, str]] = None,
) -> str:
    if not has_mode:
        return "// No mode data"
    _labels = mode_labels or {}
    _colors = mode_colors or {}
    lines = []
    for tool in tool_names:
        md = mode_data.get(tool, {})
        present = {k: v for k, v in md.items() if k != "none" and v > 0}
        if not present:
            continue
        chart_id = f"modeChart_{tool}"
        labels = json.dumps([_labels.get(k, k.capitalize()) for k in present])
        values = json.dumps(list(present.values()))
        colors = json.dumps([_colors.get(k, "#6b7280") for k in present])
        lines.append(f"""
new Chart(document.getElementById('{chart_id}'), {{
  type: 'doughnut',
  data: {{
    labels: {labels},
    datasets: [{{ data: {values}, backgroundColor: {colors}, borderWidth: 2, borderColor: '#1a1d27', hoverOffset: 6 }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ position: 'bottom', labels: {{ padding: 12, usePointStyle: true }} }} }}
  }}
}});""")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a personal AI usage insights HTML report."
    )
    parser.add_argument(
        "--output",
        default="~/Desktop/myusage-report.html",
        help="Output path for the HTML report (default: ~/Desktop/myusage-report.html)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=180,
        help="Limit history to the most recent N days (default: 180 = 6 months; use 0 for all time)",
    )
    parser.add_argument(
        "--claude-dir",
        default="~/.claude/projects/",
        help="Override Claude Code history directory",
    )
    parser.add_argument(
        "--vscode-dir",
        default="~/Library/Application Support/Code/User/workspaceStorage/",
        help="Override Copilot VS Code history directory",
    )
    parser.add_argument(
        "--copilot-cli-dir",
        default="~/.copilot/session-state/",
        help="Override Copilot CLI event directory",
    )
    parser.add_argument(
        "--chartjs-src",
        default=None,
        help="Path to a local Chart.js source file to inline instead of fetching from CDN (useful for offline/testing)",
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        default=False,
        help="Extract structured session data as JSON to stdout (for Claude to read). Does not generate HTML.",
    )
    parser.add_argument(
        "--insights",
        default=None,
        metavar="PATH",
        help="Path to a JSON file containing AI-generated narrative insights to embed in the report.",
    )
    args = parser.parse_args()

    # --extract mode skips the output path validation
    if not args.extract:
        output_path = os.path.expanduser(args.output)
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.isdir(output_dir):
            print(f"Error: output directory does not exist: {output_dir}", file=sys.stderr)
            sys.exit(2)

    # Cutoff time for --days filter (0 means all time)
    cutoff: Optional[datetime] = None
    if args.days:  # 0 or None = no cutoff
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=args.days)
    if not args.days:
        args.days = None  # normalize 0 → None so window_note shows "all-time history"

    all_sessions: List[Session] = []

    # --- Claude Code ---
    claude_dir_display = args.claude_dir
    print(f"Scanning Claude Code history: {claude_dir_display} ...", end=" ", flush=True, file=sys.stderr)
    try:
        cc_sessions = parse_claude_code(args.claude_dir)
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(2)
    if cutoff:
        cc_sessions = [s for s in cc_sessions if s.start_time >= cutoff]
    print(f"{len(cc_sessions)} sessions found", file=sys.stderr)
    all_sessions.extend(cc_sessions)

    # --- Copilot VS Code ---
    vscode_dir_display = args.vscode_dir
    print(f"Scanning Copilot VS Code history: {vscode_dir_display} ...", end=" ", flush=True, file=sys.stderr)
    try:
        vs_sessions = parse_copilot_vscode(args.vscode_dir)
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(2)
    if cutoff:
        vs_sessions = [s for s in vs_sessions if s.start_time >= cutoff]
    print(f"{len(vs_sessions)} sessions found", file=sys.stderr)
    all_sessions.extend(vs_sessions)

    # --- Copilot CLI ---
    cli_dir_display = args.copilot_cli_dir
    print(f"Scanning Copilot CLI history: {cli_dir_display} ...", end=" ", flush=True, file=sys.stderr)
    try:
        cli_sessions = parse_copilot_cli(args.copilot_cli_dir)
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(2)
    if cutoff:
        cli_sessions = [s for s in cli_sessions if s.start_time >= cutoff]
    print(f"{len(cli_sessions)} sessions found", file=sys.stderr)
    all_sessions.extend(cli_sessions)

    # --- Codex ---
    print(f"Scanning Codex history: {CODEX_HOME_DIR} ...", end=" ", flush=True, file=sys.stderr)
    try:
        db_path = discover_codex_database()
        if db_path:
            codex_sessions = parse_codex_database(db_path)
            if cutoff:
                codex_sessions = [s for s in codex_sessions if s.start_time >= cutoff]
            print(f"{len(codex_sessions)} sessions found", file=sys.stderr)
            all_sessions.extend(codex_sessions)
        else:
            print("database not found, skipping", file=sys.stderr)
    except Exception as exc:
        print(f"\nWarning: {exc}", file=sys.stderr)

    if not all_sessions:
        print("\nNo chat history found. Checked:", file=sys.stderr)
        print(f"  Claude Code:     {os.path.expanduser(args.claude_dir)}", file=sys.stderr)
        print(f"  Copilot VS Code: {os.path.expanduser(args.vscode_dir)}", file=sys.stderr)
        print(f"  Copilot CLI:     {os.path.expanduser(args.copilot_cli_dir)}", file=sys.stderr)
        print(f"  Codex:           {CODEX_HOME_DIR}", file=sys.stderr)
        sys.exit(1)

    report = build_report(all_sessions)

    # --- --extract mode: print JSON to stdout and exit ---
    if args.extract:
        print(extract_data(report, all_sessions, days_filter=args.days))
        sys.exit(0)

    # --- Load insights if --insights provided ---
    insights: Optional[dict] = None
    if args.insights:
        insights = load_insights(args.insights)

    # Load local Chart.js source if provided (e.g. for offline/testing)
    chartjs_src: Optional[str] = None
    if args.chartjs_src:
        chartjs_src_path = os.path.expanduser(args.chartjs_src)
        try:
            with open(chartjs_src_path, "r", encoding="utf-8") as fh:
                chartjs_src = fh.read()
            print(f"Using local Chart.js from: {chartjs_src_path}", file=sys.stderr)
        except OSError as exc:
            print(f"Error: Cannot read --chartjs-src file: {exc}", file=sys.stderr)
            sys.exit(2)

    output_path = os.path.expanduser(args.output)
    try:
        render_html(report, output_path, chartjs_src=chartjs_src, insights=insights, days_filter=args.days)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)
    except OSError as exc:
        print(f"Error: Failed to write report to {output_path}: {exc}", file=sys.stderr)
        sys.exit(2)

    print(f"Report written to: {output_path}")
    sys.exit(0)


if __name__ == "__main__":
    main()
