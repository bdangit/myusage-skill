import unittest
from pathlib import Path
from unittest.mock import patch
import sys
import tempfile

# Import the functions to test
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "myusage" / "scripts"))
from generate_report import discover_codex_database


class TestCodexUS1NoDB(unittest.TestCase):
    def test_discover_codex_database_missing(self):
        """EVAL-002: discover_codex_database must return None gracefully when database is missing."""
        # Create a temporary non-existent directory (delete it after creation)
        with tempfile.TemporaryDirectory() as temp_dir:
            non_existent_dir = Path(temp_dir) / "non_existent"
            # non_existent_dir does not exist
            
            # Mock CODEX_HOME_DIR to point to the non-existent directory
            with patch("generate_report.CODEX_HOME_DIR", non_existent_dir):
                result = discover_codex_database()
                
                # Verify it returns None gracefully, not an exception
                self.assertIsNone(result, "discover_codex_database() should return None when directory doesn't exist")
