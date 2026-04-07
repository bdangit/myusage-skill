import unittest
from pathlib import Path
import sys

# Import the functions to test
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "myusage" / "scripts"))
from generate_report import parse_codex_database


class TestCodexUS3CrossPlatform(unittest.TestCase):
    def test_user_message_counting(self):
        """EVAL-005: Message counts must match fixture data."""
        fixture_db = Path(__file__).parent / "fixtures" / "codex" / "state_1.sqlite"
        
        # Call parse_codex_database
        sessions = parse_codex_database(fixture_db)
        
        # Expected message counts
        expected_counts = {
            "uuid-001": 8,
            "uuid-002": 10,
            "uuid-003": 4,
        }
        
        # Verify message counts for each session
        for session_id, expected_count in expected_counts.items():
            session = next((s for s in sessions if s.session_id == session_id), None)
            self.assertIsNotNone(session, f"Session {session_id} should exist")
            self.assertEqual(
                session.message_count, 
                expected_count,
                f"Session {session_id}: expected {expected_count} messages, got {session.message_count}"
            )
