import unittest
from pathlib import Path
from unittest.mock import patch
import sys

# Import the functions to test
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "myusage" / "scripts"))
from generate_report import discover_codex_database


class TestCodexUS1(unittest.TestCase):
    def test_discover_codex_database(self):
        """EVAL-001: discover_codex_database must return the fixture state_1.sqlite path."""
        fixture_dir = Path(__file__).parent / "fixtures" / "codex"
        
        # Mock CODEX_HOME_DIR to point to the fixture directory
        with patch("generate_report.CODEX_HOME_DIR", fixture_dir):
            result = discover_codex_database()
            
            # Verify it returns the correct path
            self.assertIsNotNone(result, "discover_codex_database() should return a path, not None")
            self.assertTrue(result.exists(), f"Returned path should exist: {result}")
            self.assertEqual(result.name, "state_1.sqlite", "Should return state_1.sqlite")
            self.assertEqual(result, fixture_dir / "state_1.sqlite", "Should return the fixture database path")
