"""
EVAL-002: PRU cost computation for Copilot CLI sessions.

Parses both CLI fixture sessions and verifies that build_report correctly
computes effective PRUs, estimated cost, and token data for each.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from generate_report import parse_copilot_cli, build_report

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')
CLI_DIR = os.path.join(FIXTURES, 'copilot_cli')


class TestPRUCLI(unittest.TestCase):

    def setUp(self):
        sessions = parse_copilot_cli(CLI_DIR)
        self.assertGreater(
            len(sessions), 0,
            f"No sessions parsed from {CLI_DIR}; check fixture path.",
        )
        build_report(sessions)
        self.sessions_by_id = {s.session_id: s for s in sessions}

    def _get_session(self, session_id):
        self.assertIn(
            session_id,
            self.sessions_by_id,
            f"Session '{session_id}' not found in parsed results.",
        )
        return self.sessions_by_id[session_id]

    # ------------------------------------------------------------------ #
    # Tests that apply to every parsed session
    # ------------------------------------------------------------------ #

    def test_all_sessions_have_positive_effective_prus(self):
        """Every CLI session must have effective_prus > 0 after build_report."""
        for sid, session in self.sessions_by_id.items():
            with self.subTest(session_id=sid):
                self.assertIsNotNone(
                    session.effective_prus,
                    f"effective_prus is None for session '{sid}'",
                )
                self.assertGreater(
                    session.effective_prus,
                    0,
                    f"effective_prus not > 0 for session '{sid}'",
                )

    def test_all_sessions_have_positive_estimated_cost_usd(self):
        """Every CLI session must have estimated_cost_usd > 0 after build_report."""
        for sid, session in self.sessions_by_id.items():
            with self.subTest(session_id=sid):
                self.assertIsNotNone(
                    session.estimated_cost_usd,
                    f"estimated_cost_usd is None for session '{sid}'",
                )
                self.assertGreater(
                    session.estimated_cost_usd,
                    0,
                    f"estimated_cost_usd not > 0 for session '{sid}'",
                )

    def test_all_sessions_have_input_tokens(self):
        """CLI fixtures contain assistant.usage events; input_tokens must not be None."""
        for sid, session in self.sessions_by_id.items():
            with self.subTest(session_id=sid):
                self.assertIsNotNone(
                    session.input_tokens,
                    f"input_tokens is None for session '{sid}'",
                )

    def test_all_sessions_have_output_tokens(self):
        """CLI fixtures contain assistant.usage events; output_tokens must not be None."""
        for sid, session in self.sessions_by_id.items():
            with self.subTest(session_id=sid):
                self.assertIsNotNone(
                    session.output_tokens,
                    f"output_tokens is None for session '{sid}'",
                )

    def test_all_sessions_tool_is_copilot_cli(self):
        """Every parsed session must carry tool == 'copilot_cli'."""
        for sid, session in self.sessions_by_id.items():
            with self.subTest(session_id=sid):
                self.assertEqual(
                    session.tool,
                    "copilot_cli",
                    f"Unexpected tool value for session '{sid}': {session.tool}",
                )

    # ------------------------------------------------------------------ #
    # Per-session message_count assertions
    # ------------------------------------------------------------------ #

    def test_session_cli_001_message_count(self):
        """session-cli-001 fixture has 3 user.message events; message_count must be 3."""
        session = self._get_session("session-cli-001")
        self.assertEqual(
            session.message_count,
            3,
            f"Expected message_count 3, got {session.message_count}",
        )

    def test_session_cli_002_message_count(self):
        """session-cli-002 fixture has 6 user.message events; message_count must be 6."""
        session = self._get_session("session-cli-002")
        self.assertEqual(
            session.message_count,
            6,
            f"Expected message_count 6, got {session.message_count}",
        )


if __name__ == "__main__":
    unittest.main()
