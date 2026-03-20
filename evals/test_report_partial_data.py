"""
test_report_partial_data.py — EVAL-006: Report generation with partial or empty data.

Two sub-tests:
  Test A — Claude-only: Only Claude Code fixtures are parsed; Copilot cost
            columns should show N/A, and the cost footnote must still appear.
  Test B — Empty sessions: build_report([]) must not raise and must produce
            non-empty HTML output.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from generate_report import (
    parse_claude_code,
    build_report,
    render_html,
)

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')
CLAUDE_FIXTURES = os.path.join(FIXTURES, 'claude_code')

CHARTJS_STUB = "/* stub */"


class TestEval006ClaudeOnly(unittest.TestCase):
    """
    EVAL-006 Test A: Parse only Claude Code fixtures.

    Claude sessions carry token-based costs; the Copilot PRU/cost columns
    should either be absent or show N/A because no Copilot sessions were loaded.
    The footnote must still appear since the cost section is always rendered.
    """

    def setUp(self):
        sessions = parse_claude_code(CLAUDE_FIXTURES)
        self.assertGreater(
            len(sessions), 0,
            "Expected at least one Claude Code session from fixtures; check fixture path",
        )

        report = build_report(sessions)

        self._tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
        self._tmp_path = self._tmp.name
        self._tmp.close()

        # Should not raise
        render_html(report, self._tmp_path, chartjs_src=CHARTJS_STUB)

        with open(self._tmp_path, "r", encoding="utf-8") as fh:
            self.html = fh.read()

    def tearDown(self):
        if os.path.exists(self._tmp_path):
            os.unlink(self._tmp_path)

    def test_html_generates_without_error(self):
        """render_html must produce non-empty HTML when only Claude sessions are present."""
        self.assertTrue(
            len(self.html) > 0,
            "Rendered HTML must not be empty for Claude-only sessions",
        )

    def test_copilot_tool_absent_when_no_copilot_sessions(self):
        """
        With no Copilot sessions, Copilot tool rows do not appear in the table.
        Tools with no data are omitted entirely rather than shown as N/A rows.
        """
        self.assertNotIn(
            "copilot_vscode",
            self.html,
            "copilot_vscode tool key must not appear when no Copilot sessions were parsed",
        )
        self.assertNotIn(
            "copilot_cli",
            self.html,
            "copilot_cli tool key must not appear when no Copilot sessions were parsed",
        )

    def test_cost_footnote_present(self):
        """The 'estimated' footnote must appear in any report that includes cost columns."""
        self.assertIn(
            "estimated",
            self.html,
            "HTML should contain 'estimated' as part of the cost footnote",
        )


class TestEval006EmptySessions(unittest.TestCase):
    """
    EVAL-006 Test B: build_report([]) with empty session list.

    No exception should be raised and the rendered HTML must be non-empty.
    """

    def setUp(self):
        self._tmp_path = None

    def tearDown(self):
        if self._tmp_path and os.path.exists(self._tmp_path):
            os.unlink(self._tmp_path)

    def test_empty_sessions_no_exception(self):
        """build_report and render_html must not raise for an empty session list."""
        report = build_report([])

        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
        self._tmp_path = tmp.name
        tmp.close()

        try:
            render_html(report, self._tmp_path, chartjs_src=CHARTJS_STUB)
        except Exception as exc:  # noqa: BLE001
            self.fail(
                f"render_html raised an unexpected exception for empty sessions: {exc}"
            )

    def test_empty_sessions_html_non_empty(self):
        """The HTML output for an empty report must still be a non-empty string."""
        report = build_report([])

        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
        self._tmp_path = tmp.name
        tmp.close()

        render_html(report, self._tmp_path, chartjs_src=CHARTJS_STUB)

        with open(self._tmp_path, "r", encoding="utf-8") as fh:
            html = fh.read()

        self.assertGreater(
            len(html),
            0,
            "Rendered HTML must not be empty even when no sessions are present",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
