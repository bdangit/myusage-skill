import unittest
from pathlib import Path
import sys

# Import the functions to test
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "myusage" / "scripts"))
from generate_report import parse_codex_database


class TestCodexUS2Categorization(unittest.TestCase):
    def test_parse_codex_database(self):
        """EVAL-003: parse_codex_database must return 3 Session objects with tool='codex'."""
        fixture_db = Path(__file__).parent / "fixtures" / "codex" / "state_1.sqlite"
        
        # Call parse_codex_database
        sessions = parse_codex_database(fixture_db)
        
        # Verify 3 sessions are returned
        self.assertEqual(len(sessions), 3, f"Expected 3 sessions, got {len(sessions)}")
        
        # Verify tool='codex' on all sessions
        for session in sessions:
            self.assertEqual(session.tool, "codex", f"Session {session.session_id} should have tool='codex'")
        
        # Verify session IDs match what we expect
        session_ids = {s.session_id for s in sessions}
        expected_ids = {"uuid-001", "uuid-002", "uuid-003"}
        self.assertEqual(session_ids, expected_ids, f"Session IDs should be {expected_ids}, got {session_ids}")
