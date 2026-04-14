#!/usr/bin/env python3
"""Create synthetic Codex fixtures for Phase 3 evals."""

import sqlite3
import json
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent
FIXTURES_DIR = BASE_DIR / "evals" / "fixtures" / "codex"
ROLLOUTS_DIR = FIXTURES_DIR / "rollouts"

def create_database():
    """Create state_1.sqlite with threads table and 3 sessions."""
    db_path = FIXTURES_DIR / "state_1.sqlite"
    
    # Remove existing database if present
    if db_path.exists():
        db_path.unlink()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create threads table
    cursor.execute("""
        CREATE TABLE threads (
            id TEXT PRIMARY KEY,
            created_at TEXT,
            updated_at TEXT,
            working_directory TEXT,
            tokens_used INTEGER,
            model TEXT,
            cli_version TEXT,
            source TEXT,
            approval_mode TEXT,
            rollout_path TEXT
        )
    """)
    
    # Insert 3 sessions
    sessions = [
        {
            "id": "uuid-001",
            "created_at": "2026-03-01T10:00:00Z",
            "updated_at": "2026-03-01T10:30:00Z",
            "working_directory": None,
            "tokens_used": 1500,
            "model": "claude-opus-4.6",
            "cli_version": "1.2.3",
            "source": "cli",
            "approval_mode": "agentic",
            "rollout_path": "rollouts/session-001.jsonl"
        },
        {
            "id": "uuid-002",
            "created_at": "2026-03-02T14:00:00Z",
            "updated_at": "2026-03-02T15:00:00Z",
            "working_directory": None,
            "tokens_used": 2800,
            "model": None,  # NULL to test resolution from rollout
            "cli_version": "1.2.3",
            "source": "vscode",
            "approval_mode": "on-request",
            "rollout_path": "rollouts/session-002.jsonl"
        },
        {
            "id": "uuid-003",
            "created_at": "2026-03-03T08:00:00Z",
            "updated_at": "2026-03-03T09:15:00Z",
            "working_directory": None,
            "tokens_used": 900,
            "model": "claude-haiku-4.5",
            "cli_version": "1.2.3",
            "source": "cli",
            "approval_mode": "network-disabled",
            "rollout_path": "rollouts/session-003.jsonl"
        }
    ]
    
    for session in sessions:
        cursor.execute("""
            INSERT INTO threads (
                id, created_at, updated_at, working_directory, tokens_used,
                model, cli_version, source, approval_mode, rollout_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["id"], session["created_at"], session["updated_at"],
            session["working_directory"], session["tokens_used"], session["model"],
            session["cli_version"], session["source"], session["approval_mode"],
            session["rollout_path"]
        ))
    
    conn.commit()
    conn.close()
    print(f"✅ Created {db_path} with 3 sessions")

def create_rollout_files():
    """Create 3 JSONL rollout files."""
    
    # Session 001: 8 user messages, model in turn_context
    session_001 = [
        {"type": "session_meta", "session_id": "uuid-001", "timestamp": "2026-03-01T10:00:00Z"},
        {"type": "turn_context", "model": "claude-opus-4.6", "turn": 0},
        {"type": "response_item", "role": "user", "content": "Debug the API timeout"},
        {"type": "response_item", "role": "assistant", "content": "I'll help debug the API timeout issue."},
        {"type": "response_item", "role": "user", "content": "Check the connection pool settings"},
        {"type": "response_item", "role": "assistant", "content": "Looking at connection pool settings now."},
        {"type": "response_item", "role": "user", "content": "What's the current timeout value?"},
        {"type": "response_item", "role": "assistant", "content": "Current timeout is 30 seconds."},
        {"type": "response_item", "role": "user", "content": "Increase it to 60 seconds"},
        {"type": "response_item", "role": "assistant", "content": "Updated timeout to 60 seconds."},
        {"type": "response_item", "role": "user", "content": "Test the API endpoint"},
        {"type": "response_item", "role": "assistant", "content": "Testing endpoint now."},
        {"type": "response_item", "role": "user", "content": "Check error logs"},
        {"type": "response_item", "role": "assistant", "content": "Checking logs for errors."},
        {"type": "response_item", "role": "user", "content": "Add retry logic"},
        {"type": "response_item", "role": "assistant", "content": "Added exponential backoff retry logic."},
        {"type": "response_item", "role": "user", "content": "Run integration tests"},
        {"type": "response_item", "role": "assistant", "content": "All integration tests passing."}
    ]
    
    # Session 002: 10 user messages, model in turn_context (resolves NULL from DB)
    session_002 = [
        {"type": "session_meta", "session_id": "uuid-002", "timestamp": "2026-03-02T14:00:00Z"},
        {"type": "turn_context", "model": "claude-opus-4.6", "turn": 0},
        {"type": "response_item", "role": "user", "content": "Generate test cases"},
        {"type": "response_item", "role": "assistant", "content": "I'll generate comprehensive test cases."},
        {"type": "response_item", "role": "user", "content": "Cover edge cases"},
        {"type": "response_item", "role": "assistant", "content": "Adding edge case coverage."},
        {"type": "response_item", "role": "user", "content": "Add boundary value tests"},
        {"type": "response_item", "role": "assistant", "content": "Created boundary value tests."},
        {"type": "response_item", "role": "user", "content": "Include negative scenarios"},
        {"type": "response_item", "role": "assistant", "content": "Added negative test scenarios."},
        {"type": "response_item", "role": "user", "content": "Test null handling"},
        {"type": "response_item", "role": "assistant", "content": "Added null handling tests."},
        {"type": "response_item", "role": "user", "content": "Add performance tests"},
        {"type": "response_item", "role": "assistant", "content": "Created performance benchmarks."},
        {"type": "response_item", "role": "user", "content": "Test concurrent access"},
        {"type": "response_item", "role": "assistant", "content": "Added concurrency tests."},
        {"type": "response_item", "role": "user", "content": "Verify data integrity"},
        {"type": "response_item", "role": "assistant", "content": "Data integrity tests complete."},
        {"type": "response_item", "role": "user", "content": "Add regression tests"},
        {"type": "response_item", "role": "assistant", "content": "Regression test suite added."},
        {"type": "response_item", "role": "user", "content": "Review test coverage"},
        {"type": "response_item", "role": "assistant", "content": "Test coverage at 95%."}
    ]
    
    # Session 003: 4 user messages
    session_003 = [
        {"type": "session_meta", "session_id": "uuid-003", "timestamp": "2026-03-03T08:00:00Z"},
        {"type": "turn_context", "model": "claude-haiku-4.5", "turn": 0},
        {"type": "response_item", "role": "user", "content": "Plan the refactor"},
        {"type": "response_item", "role": "assistant", "content": "I'll create a refactoring plan."},
        {"type": "response_item", "role": "user", "content": "Identify code smells"},
        {"type": "response_item", "role": "assistant", "content": "Found duplicate code and long methods."},
        {"type": "response_item", "role": "user", "content": "Suggest improvements"},
        {"type": "response_item", "role": "assistant", "content": "Extract methods and use composition."},
        {"type": "response_item", "role": "user", "content": "Create task list"},
        {"type": "response_item", "role": "assistant", "content": "Task list created with 12 items."}
    ]
    
    # Write JSONL files
    rollout_files = [
        ("session-001.jsonl", session_001),
        ("session-002.jsonl", session_002),
        ("session-003.jsonl", session_003)
    ]
    
    for filename, events in rollout_files:
        filepath = ROLLOUTS_DIR / filename
        with open(filepath, 'w') as f:
            for event in events:
                f.write(json.dumps(event) + '\n')
        
        # Count user messages
        user_count = sum(1 for e in events if e.get("type") == "response_item" and e.get("role") == "user")
        print(f"✅ Created {filepath} with {user_count} user messages")

if __name__ == "__main__":
    # Ensure directories exist
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    ROLLOUTS_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Creating Codex Phase 3 fixtures...")
    create_database()
    create_rollout_files()
    print("\n✅ All fixtures created successfully")
