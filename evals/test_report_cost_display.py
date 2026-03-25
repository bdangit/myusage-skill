"""
test_report_cost_display.py — EVAL-005: Cost display in generated HTML report.

Loads sessions from all three fixture sources, builds a report, renders HTML
using a stub Chart.js source, then asserts that cost-related elements are present
and correctly formatted in the output.
"""

import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'myusage', 'scripts'))
from generate_report import (
    parse_claude_code,
    parse_copilot_vscode,
    parse_copilot_cli,
    build_report,
    render_html,
)

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')
CLAUDE_FIXTURES = os.path.join(FIXTURES, 'claude_code')
VSCODE_FIXTURES = os.path.join(FIXTURES, 'copilot_vscode')
CLI_FIXTURES = os.path.join(FIXTURES, 'copilot_cli')

CHARTJS_STUB = "/* stub */"


class TestEval005CostDisplay(unittest.TestCase):
    """
    EVAL-005: Verify that the rendered HTML includes cost display elements
    when sessions from all three fixture sources are loaded.
    """

    def setUp(self):
        sessions = []
        sessions.extend(parse_claude_code(CLAUDE_FIXTURES))
        sessions.extend(parse_copilot_vscode(VSCODE_FIXTURES))
        sessions.extend(parse_copilot_cli(CLI_FIXTURES))

        self.assertGreater(
            len(sessions), 0,
            "Expected at least one session from fixtures; check fixture paths",
        )

        report = build_report(sessions)

        self._tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
        self._tmp_path = self._tmp.name
        self._tmp.close()

        render_html(report, self._tmp_path, chartjs_src=CHARTJS_STUB)

        with open(self._tmp_path, "r", encoding="utf-8") as fh:
            self.html = fh.read()

    def tearDown(self):
        if os.path.exists(self._tmp_path):
            os.unlink(self._tmp_path)

    def test_footnote_estimated_present(self):
        """The cost footnote should contain the word 'estimated'."""
        self.assertIn(
            "estimated",
            self.html,
            "HTML should contain 'estimated' as part of the cost footnote",
        )

    def test_dollar_cost_value_present(self):
        """At least one cost value formatted as '$<digits>' should appear."""
        match = re.search(r'\$\d', self.html)
        self.assertIsNotNone(
            match,
            "HTML should contain at least one cost value starting with '$' followed by digits",
        )

    def test_effective_prus_column_present(self):
        """The 'Effective PRUs' column header should appear (Copilot sessions carry PRU data)."""
        self.assertIn(
            "Effective PRUs",
            self.html,
            "HTML should contain 'Effective PRUs' column header",
        )

    def test_est_cost_column_header_present(self):
        """The 'Est. Cost' column header should appear in the per-tool statistics table."""
        self.assertIn(
            "Est. Cost",
            self.html,
            "HTML should contain 'Est. Cost' column header in the statistics table",
        )

    def test_at_least_one_real_cost_not_all_na(self):
        """
        The HTML must contain at least one real cost value (not N/A).
        Copilot sessions should produce PRU-based estimates.
        """
        # Find all table cells that could be cost values ($X.XXXX) or N/A
        cost_cell_pattern = re.compile(r'\$[\d]+\.[\d]+')
        real_cost_matches = cost_cell_pattern.findall(self.html)
        self.assertGreater(
            len(real_cost_matches),
            0,
            "HTML should contain at least one real cost value (e.g. '$0.2000'), "
            "not all N/A — Copilot sessions should produce PRU-based estimates. "
            f"HTML snippet around 'Est. Cost': "
            + _html_snippet(self.html, "Est. Cost", 400),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _html_snippet(html: str, marker: str, context: int = 200) -> str:
    """Return a snippet of HTML around the first occurrence of marker."""
    idx = html.find(marker)
    if idx == -1:
        return f"(marker '{marker}' not found in HTML)"
    start = max(0, idx - 50)
    end = min(len(html), idx + context)
    return f"...{html[start:end]}..."


if __name__ == "__main__":
    unittest.main(verbosity=2)
