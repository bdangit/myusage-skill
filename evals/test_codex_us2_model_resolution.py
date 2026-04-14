import unittest
from pathlib import Path
import sys

# Import the functions to test
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "myusage" / "scripts"))
from generate_report import parse_codex_database


class TestCodexUS2ModelResolution(unittest.TestCase):
    def test_model_resolution_from_rollout(self):
        """EVAL-004: Model must resolve from rollout when DB is NULL."""
        fixture_db = Path(__file__).parent / "fixtures" / "codex" / "state_1.sqlite"
        
        # Call parse_codex_database
        sessions = parse_codex_database(fixture_db)
        
        # Find Session 2 (index 1) — uuid-002
        session_2 = next((s for s in sessions if s.session_id == "uuid-002"), None)
        self.assertIsNotNone(session_2, "Session uuid-002 should be in the results")
        
        # Verify model is resolved to a non-empty string
        self.assertIsNotNone(session_2.model, "Session uuid-002 model should not be None")
        self.assertIsInstance(session_2.model, str, "Model should be a string")
        self.assertTrue(len(session_2.model) > 0, "Model should not be empty")
        
        # Verify it's a reasonable model name (should be resolved from rollout file)
        # The fixture has "claude-haiku-4.5" in the turn_context of session-002.jsonl
        self.assertIn("claude", session_2.model.lower(), 
                      f"Model should contain 'claude', got: {session_2.model}")
