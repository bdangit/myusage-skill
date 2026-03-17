"""
EVAL-004: Claude Code cost estimation tests.

Parses all fixtures in evals/fixtures/claude_code/project-alpha/ through
parse_claude_code, runs build_report, then validates cost estimates per session.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from generate_report import parse_claude_code, build_report, TOKEN_PRICES  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestClaudeCodeCostEstimation(unittest.TestCase):
    """EVAL-004: Validate per-session cost estimates for Claude Code fixtures."""

    @classmethod
    def setUpClass(cls):
        fixture_dir = os.path.join(FIXTURES, "claude_code", "project-alpha")
        sessions = parse_claude_code(fixture_dir)
        # build_report calls compute_session_costs internally, which mutates sessions
        cls.report = build_report(sessions)
        # Collect the post-mutation sessions from the snapshot
        cls.sessions = cls.report.snapshots.get("claude_code", None)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _expected_cost(self, session):
        """Compute the expected cost from token counts and TOKEN_PRICES."""
        prices = TOKEN_PRICES[session.model]
        return (
            session.input_tokens / 1_000_000 * prices["input"]
            + session.output_tokens / 1_000_000 * prices["output"]
        )

    # ------------------------------------------------------------------
    # Sanity: fixture data loaded at all
    # ------------------------------------------------------------------

    def test_sessions_loaded(self):
        """At least one claude_code session must be present."""
        self.assertIsNotNone(
            self.sessions,
            "No 'claude_code' snapshot found — check that the fixture directory exists.",
        )
        self.assertGreater(
            len(self.sessions.sessions),
            0,
            "Expected at least one session from project-alpha fixtures.",
        )

    # ------------------------------------------------------------------
    # Per-session assertions
    # ------------------------------------------------------------------

    def test_tool_is_claude_code(self):
        """Every session must have tool == 'claude_code'."""
        for s in self.sessions.sessions:
            with self.subTest(session_id=s.session_id):
                self.assertEqual(
                    s.tool,
                    "claude_code",
                    f"Session {s.session_id!r} has unexpected tool {s.tool!r}.",
                )

    def test_no_negative_cost(self):
        """No session may have a negative estimated_cost_usd."""
        for s in self.sessions.sessions:
            with self.subTest(session_id=s.session_id):
                if s.estimated_cost_usd is not None:
                    self.assertGreaterEqual(
                        s.estimated_cost_usd,
                        0.0,
                        f"Session {s.session_id!r} has negative cost: {s.estimated_cost_usd}.",
                    )

    def test_cost_set_when_tokens_and_model_known(self):
        """Sessions with token data and a known model must have estimated_cost_usd set."""
        for s in self.sessions.sessions:
            with self.subTest(session_id=s.session_id):
                if (
                    s.input_tokens is not None
                    and s.output_tokens is not None
                    and s.model in TOKEN_PRICES
                ):
                    self.assertIsNotNone(
                        s.estimated_cost_usd,
                        f"Session {s.session_id!r} (model={s.model!r}) should have a cost estimate.",
                    )

    def test_cost_within_ten_percent(self):
        """Cost estimate must match manual calculation within ±10%."""
        for s in self.sessions.sessions:
            with self.subTest(session_id=s.session_id):
                if (
                    s.input_tokens is not None
                    and s.output_tokens is not None
                    and s.model in TOKEN_PRICES
                ):
                    self.assertIsNotNone(s.estimated_cost_usd)
                    expected = self._expected_cost(s)
                    actual = s.estimated_cost_usd
                    # Allow ±10% relative tolerance (use absolute tolerance for near-zero)
                    tolerance = max(expected * 0.10, 1e-9)
                    self.assertAlmostEqual(
                        actual,
                        expected,
                        delta=tolerance,
                        msg=(
                            f"Session {s.session_id!r}: cost {actual:.8f} differs from "
                            f"expected {expected:.8f} by more than 10%."
                        ),
                    )

    # ------------------------------------------------------------------
    # Fixture sanity: at least one session must have a cost
    # ------------------------------------------------------------------

    def test_at_least_one_session_has_cost(self):
        """At least one session in the fixture set must have a non-None cost estimate."""
        costs = [
            s.estimated_cost_usd
            for s in self.sessions.sessions
            if s.estimated_cost_usd is not None
        ]
        self.assertGreater(
            len(costs),
            0,
            "No session in the fixture set has a cost estimate — check fixture data.",
        )

    # ------------------------------------------------------------------
    # Spot-check: known token totals per session (exact math)
    # ------------------------------------------------------------------

    def _get_session(self, session_id):
        for s in self.sessions.sessions:
            if s.session_id == session_id:
                return s
        return None

    def test_codegen_cost_exact(self):
        """
        session-codegen (sess-codegen-001): claude-opus-4-6
        Turns: (500i+600o), (700i+900o), (900i+1200o)
        Total: 2100 input, 2700 output
        Expected cost = 2100/1e6 * 15.00 + 2700/1e6 * 75.00
                      = 0.0315 + 0.2025 = 0.2340 USD
        """
        s = self._get_session("sess-codegen-001")
        self.assertIsNotNone(s, "sess-codegen-001 not found in parsed sessions.")
        self.assertEqual(s.input_tokens, 2100)
        self.assertEqual(s.output_tokens, 2700)
        self.assertEqual(s.model, "claude-opus-4-6")
        expected = 2100 / 1_000_000 * 15.00 + 2700 / 1_000_000 * 75.00
        self.assertAlmostEqual(s.estimated_cost_usd, expected, places=9)

    def test_debug_cost_exact(self):
        """
        session-debug (sess-debug-001): claude-opus-4-6
        Turns: (400i+300o), (600i+500o), (800i+700o), (900i+300o)
        Total: 2700 input, 1800 output
        Expected cost = 2700/1e6 * 15.00 + 1800/1e6 * 75.00
                      = 0.0405 + 0.1350 = 0.1755 USD
        """
        s = self._get_session("sess-debug-001")
        self.assertIsNotNone(s, "sess-debug-001 not found in parsed sessions.")
        self.assertEqual(s.input_tokens, 2700)
        self.assertEqual(s.output_tokens, 1800)
        self.assertEqual(s.model, "claude-opus-4-6")
        expected = 2700 / 1_000_000 * 15.00 + 1800 / 1_000_000 * 75.00
        self.assertAlmostEqual(s.estimated_cost_usd, expected, places=9)

    def test_autonomous_cost_exact(self):
        """
        session-autonomous (sess-auto-001): claude-opus-4-6
        Turns: (1200i+800o), (2100i+1400o), (1800i+1200o)
        Total: 5100 input, 3400 output
        Expected cost = 5100/1e6 * 15.00 + 3400/1e6 * 75.00
                      = 0.0765 + 0.2550 = 0.3315 USD
        """
        s = self._get_session("sess-auto-001")
        self.assertIsNotNone(s, "sess-auto-001 not found in parsed sessions.")
        self.assertEqual(s.input_tokens, 5100)
        self.assertEqual(s.output_tokens, 3400)
        self.assertEqual(s.model, "claude-opus-4-6")
        expected = 5100 / 1_000_000 * 15.00 + 3400 / 1_000_000 * 75.00
        self.assertAlmostEqual(s.estimated_cost_usd, expected, places=9)

    def test_engaged_cost_exact(self):
        """
        session-engaged (sess-eng-001): claude-sonnet-4-6
        Turns: (300i+500o), (450i+600o), (600i+700o), (700i+800o),
               (800i+900o), (900i+1100o), (950i+400o)
        Total: 4700 input, 5000 output
        Expected cost = 4700/1e6 * 3.00 + 5000/1e6 * 15.00
                      = 0.0141 + 0.0750 = 0.0891 USD
        """
        s = self._get_session("sess-eng-001")
        self.assertIsNotNone(s, "sess-eng-001 not found in parsed sessions.")
        self.assertEqual(s.input_tokens, 4700)
        self.assertEqual(s.output_tokens, 5000)
        self.assertEqual(s.model, "claude-sonnet-4-6")
        expected = 4700 / 1_000_000 * 3.00 + 5000 / 1_000_000 * 15.00
        self.assertAlmostEqual(s.estimated_cost_usd, expected, places=9)


if __name__ == "__main__":
    unittest.main()
