"""
EVAL-003: Graceful handling of missing directories and empty session lists.

Verifies that parse_copilot_vscode and parse_copilot_cli return empty lists
when given a non-existent path, and that build_report([]) returns a valid
InsightsReport with total_sessions_all_tools == 0 without raising.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from generate_report import parse_copilot_vscode, parse_copilot_cli, build_report

NONEXISTENT_DIR = "/tmp/nonexistent_dir_xyz"


class TestPRUMissingDirectory(unittest.TestCase):

    def test_parse_copilot_vscode_nonexistent_path_returns_empty_list(self):
        """parse_copilot_vscode must return [] for a path that does not exist."""
        result = parse_copilot_vscode(NONEXISTENT_DIR)
        self.assertIsInstance(result, list)
        self.assertEqual(
            result,
            [],
            f"Expected empty list, got {result!r}",
        )

    def test_parse_copilot_cli_nonexistent_path_returns_empty_list(self):
        """parse_copilot_cli must return [] for a path that does not exist."""
        result = parse_copilot_cli(NONEXISTENT_DIR)
        self.assertIsInstance(result, list)
        self.assertEqual(
            result,
            [],
            f"Expected empty list, got {result!r}",
        )

    def test_build_report_empty_sessions_does_not_raise(self):
        """build_report([]) must not raise any exception."""
        try:
            report = build_report([])
        except Exception as exc:  # pragma: no cover
            self.fail(f"build_report([]) raised an unexpected exception: {exc!r}")

    def test_build_report_empty_sessions_total_is_zero(self):
        """build_report([]) must return an InsightsReport with total_sessions_all_tools == 0."""
        report = build_report([])
        self.assertEqual(
            report.total_sessions_all_tools,
            0,
            f"Expected total_sessions_all_tools == 0, got {report.total_sessions_all_tools}",
        )

    def test_build_report_empty_sessions_snapshots_is_empty(self):
        """build_report([]) must return an InsightsReport with no tool snapshots."""
        report = build_report([])
        self.assertIsInstance(report.snapshots, dict)
        self.assertEqual(
            report.snapshots,
            {},
            f"Expected empty snapshots dict, got {report.snapshots!r}",
        )


if __name__ == "__main__":
    unittest.main()
