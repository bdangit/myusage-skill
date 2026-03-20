"""
EVAL-001: PRU cost computation for Copilot VS Code sessions.

Parses the VS Code fixture session and verifies that build_report correctly
computes effective PRUs and estimated cost using PRU_UNIT_PRICE_USD.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from generate_report import parse_copilot_vscode, build_report, PRU_UNIT_PRICE_USD

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')
VSCODE_DIR = os.path.join(FIXTURES, 'copilot_vscode')


class TestPRUVSCode(unittest.TestCase):

    def setUp(self):
        sessions = parse_copilot_vscode(VSCODE_DIR)
        self.assertGreater(
            len(sessions), 0,
            f"No sessions parsed from {VSCODE_DIR}; check fixture path.",
        )
        report = build_report(sessions)
        # Locate the specific fixture session
        target = [s for s in sessions if s.session_id == "session-vscode-001"]
        self.assertEqual(
            len(target), 1,
            "Expected exactly one session with id 'session-vscode-001'.",
        )
        self.session = target[0]

    def test_message_count_is_five(self):
        """VS Code fixture has 5 user requests; message_count must equal 5."""
        self.assertEqual(self.session.message_count, 5)

    def test_model_is_claude_haiku(self):
        """All requests use claude-haiku-4.5; session model must reflect that."""
        self.assertEqual(self.session.model, "claude-haiku-4.5")

    def test_model_request_counts_all_haiku(self):
        """model_request_counts must map claude-haiku-4.5 -> 5."""
        self.assertIsNotNone(self.session.model_request_counts)
        self.assertEqual(
            self.session.model_request_counts,
            {"claude-haiku-4.5": 5},
        )

    def test_effective_prus_is_five(self):
        """5 requests × 1.0 multiplier for claude-haiku-4.5 = 5.0 effective PRUs."""
        self.assertIsNotNone(self.session.effective_prus)
        self.assertAlmostEqual(self.session.effective_prus, 5.0, places=6)

    def test_estimated_cost_usd_within_one_percent_of_expected(self):
        """estimated_cost_usd must be within ±1% of 5 * PRU_UNIT_PRICE_USD (= $0.20)."""
        self.assertIsNotNone(self.session.estimated_cost_usd)
        expected = 5 * PRU_UNIT_PRICE_USD  # 0.20
        tolerance = expected * 0.01        # 1%
        self.assertAlmostEqual(
            self.session.estimated_cost_usd,
            expected,
            delta=tolerance,
            msg=(
                f"estimated_cost_usd {self.session.estimated_cost_usd} not within "
                f"1% of expected {expected}"
            ),
        )

    def test_tool_is_copilot_vscode(self):
        """Session tool must be 'copilot_vscode'."""
        self.assertEqual(self.session.tool, "copilot_vscode")


if __name__ == "__main__":
    unittest.main()
