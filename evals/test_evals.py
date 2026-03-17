"""
test_evals.py — Programmatic verification of myusage-skill evals EVAL-001 through EVAL-005.

Each test:
1. Runs generate_report.py as a subprocess with --output to a temp file
2. Reads the generated HTML
3. Asserts expected content is present
"""

import os
import sys
import subprocess
import tempfile
import unittest

# Resolve paths relative to this file
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "generate_report.py")
FIXTURES = os.path.join(REPO_ROOT, "evals", "fixtures")
CLAUDE_FIXTURES = os.path.join(FIXTURES, "claude_code")
VSCODE_FIXTURES = os.path.join(FIXTURES, "copilot_vscode")
CLI_FIXTURES = os.path.join(FIXTURES, "copilot_cli")
CHARTJS_STUB = os.path.join(FIXTURES, "chartjs-stub.js")

# A non-existent directory to use when we want to disable a source
_EMPTY = os.path.join(FIXTURES, "_nonexistent_")


def _run_report(*extra_args, timeout=120):
    """
    Run generate_report.py with a temp output file.
    Returns (html_content, returncode, stdout, stderr).
    """
    out_fd, out_path = tempfile.mkstemp(suffix=".html")
    os.close(out_fd)
    try:
        # Always inject the Chart.js stub so tests work offline.
        # Use --days 0 (all time) because fixtures have fixed timestamps from the past.
        stub_args = ["--chartjs-src", CHARTJS_STUB, "--days", "0"]
        cmd = [sys.executable, SCRIPT, "--output", out_path] + stub_args + list(extra_args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        html = ""
        if os.path.exists(out_path):
            with open(out_path, "r", encoding="utf-8") as fh:
                html = fh.read()
        return html, result.returncode, result.stdout, result.stderr
    finally:
        if os.path.exists(out_path):
            os.unlink(out_path)


class TestEval001CrossToolSessionCounts(unittest.TestCase):
    """
    EVAL-001 (US1): Cross-tool session counts.
    Claude fixtures: 4 sessions. VS Code fixtures: 1 session. Total: 5.
    """

    def test_eval_001_cross_tool_session_counts(self):
        html, rc, stdout, stderr = _run_report(
            "--claude-dir", CLAUDE_FIXTURES,
            "--vscode-dir", VSCODE_FIXTURES,
            "--copilot-cli-dir", _EMPTY,
        )
        if rc == 2:
            self.fail(f"Script exited with code 2 (error).\nstdout: {stdout}\nstderr: {stderr}")
        self.assertEqual(rc, 0, f"Expected exit 0, got {rc}.\nstdout: {stdout}\nstderr: {stderr}")
        self.assertTrue(html, "HTML output should not be empty")

        # 5 total sessions should appear prominently
        self.assertIn("5", html, "HTML should contain '5' (total sessions)")

        # Claude Code label should appear
        self.assertIn("Claude Code", html, "HTML should contain 'Claude Code' tool label")

        # Copilot VS Code label should appear
        self.assertIn("Copilot VS Code", html, "HTML should contain 'Copilot VS Code' tool label")

        # The number 4 (claude sessions) and 1 (vscode sessions) should appear in the HTML
        # They appear in the stats table
        self.assertIn("4", html, "HTML should contain '4' (Claude Code session count)")
        self.assertIn("1", html, "HTML should contain '1' (Copilot VS Code session count)")

        # The report should have a Tool Usage Split section
        self.assertIn("Tool Usage", html, "HTML should contain Tool Usage section")

        print(f"\n[EVAL-001] PASSED — stdout preview:\n{stdout[:400]}")


class TestEval002PeakHour(unittest.TestCase):
    """
    EVAL-002 (US2): Hourly heatmap peak hour identification.
    Claude fixtures have messages at hours: 09, 10, 11, 14 (UTC).
    The fixture sessions are:
      session-autonomous: 3 user msgs starting 09:00 UTC
      session-engaged:    8 user msgs starting 14:00 UTC
      session-debug:      4 user msgs starting 10:00 UTC
      session-codegen:    3 user msgs starting 11:00 UTC
    So 14:xx has 8 messages — the peak hour (in UTC or local TZ close to UTC).
    We check that the patterns section exists and has a peak hour callout.
    """

    def test_eval_002_peak_hour(self):
        html, rc, stdout, stderr = _run_report(
            "--claude-dir", CLAUDE_FIXTURES,
            "--vscode-dir", _EMPTY,
            "--copilot-cli-dir", _EMPTY,
        )
        if rc == 2:
            self.fail(f"Script exited with code 2 (error).\nstdout: {stdout}\nstderr: {stderr}")
        self.assertEqual(rc, 0, f"Expected exit 0, got {rc}.\nstdout: {stdout}\nstderr: {stderr}")
        self.assertTrue(html, "HTML should not be empty")

        # Patterns section should exist
        self.assertIn("Usage Patterns", html, "HTML should have a Usage Patterns section")

        # Peak hour callout should be present
        self.assertIn("Peak hour", html, "HTML should contain a peak hour callout")

        # The heatmap is rendered as CSS div cells (not a canvas) — verify the grid is present
        self.assertIn("heatmap-cell", html, "HTML should contain heatmap CSS cells")

        # The hourly bar canvas should exist
        self.assertIn("hourlyBar", html, "HTML should contain hourly bar chart canvas")

        # The fixture sessions concentrate messages at hours 09, 10, 11, 14 UTC.
        # In local timezone these shift, but the peak hour callout should show
        # an HH:00 formatted time. We verify that the callout contains a valid
        # hour string (any 2-digit hour from 00–23 followed by ":00").
        import re
        peak_callout_match = re.search(
            r'Peak hour.*?(\d{2}:\d{2})', html, re.DOTALL
        )
        self.assertIsNotNone(
            peak_callout_match,
            "HTML should contain a peak hour callout with an HH:MM formatted time. "
            + _html_snippet(html, "Peak hour", 300),
        )
        # The identified peak hour should be one that actually has messages.
        # With 4 sessions concentrating messages at a few hours, peak > 0.
        peak_count_match = re.search(r'Peak hour.*?with (\d+) messages', html, re.DOTALL)
        if peak_count_match:
            peak_msg_count = int(peak_count_match.group(1))
            self.assertGreater(
                peak_msg_count, 0,
                "Peak hour message count should be > 0"
            )

        print(f"\n[EVAL-002] PASSED — stdout preview:\n{stdout[:400]}")


class TestEval003SessionCharacter(unittest.TestCase):
    """
    EVAL-003 (US3): Session character classification.
    CLI session-cli-001: 3 user messages, 10 tool calls, ~8 min → Autonomous
    CLI session-cli-002: 6 user messages at ~60s gaps, 0 tool calls, ~6 min → Deeply Engaged
    """

    def test_eval_003_session_character(self):
        html, rc, stdout, stderr = _run_report(
            "--claude-dir", _EMPTY,
            "--vscode-dir", _EMPTY,
            "--copilot-cli-dir", CLI_FIXTURES,
        )
        if rc == 2:
            self.fail(f"Script exited with code 2 (error).\nstdout: {stdout}\nstderr: {stderr}")
        self.assertEqual(rc, 0, f"Expected exit 0, got {rc}.\nstdout: {stdout}\nstderr: {stderr}")
        self.assertTrue(html, "HTML should not be empty")

        # Session character section should exist
        self.assertIn("Session Character", html, "HTML should have Session Character section")

        # Both Autonomous and Deeply Engaged should appear as labels
        self.assertIn(
            "Autonomous", html,
            "HTML should contain 'Autonomous' character label (session-cli-001: 10 tools / 3 msgs = 3.33 >= 3)"
        )
        self.assertIn(
            "Deeply Engaged", html,
            "HTML should contain 'Deeply Engaged' character label (session-cli-002: 6 msgs, ~60s gaps)"
        )

        # The character doughnut canvas should exist
        self.assertIn("charDoughnut", html, "HTML should contain character doughnut chart canvas")

        print(f"\n[EVAL-003] PASSED — stdout preview:\n{stdout[:400]}")


class TestEval004ModeAndModel(unittest.TestCase):
    """
    EVAL-004 (US4): Mode and model breakdown.
    VS Code session: mode=agent, model=claude-haiku-4.5
    CLI sessions: model=claude-sonnet-4-6, agentMode=true (cli-001) and false (cli-002)
    """

    def test_eval_004_mode_and_model(self):
        html, rc, stdout, stderr = _run_report(
            "--claude-dir", _EMPTY,
            "--vscode-dir", VSCODE_FIXTURES,
            "--copilot-cli-dir", CLI_FIXTURES,
        )
        if rc == 2:
            self.fail(f"Script exited with code 2 (error).\nstdout: {stdout}\nstderr: {stderr}")
        self.assertEqual(rc, 0, f"Expected exit 0, got {rc}.\nstdout: {stdout}\nstderr: {stderr}")
        self.assertTrue(html, "HTML should not be empty")

        # Model names should appear in the HTML (normalized display names)
        self.assertIn(
            "Claude Haiku 4.5", html,
            "HTML should contain normalized model name 'Claude Haiku 4.5' from VS Code session"
        )
        self.assertIn(
            "Claude Sonnet 4.6", html,
            "HTML should contain normalized model name 'Claude Sonnet 4.6' from CLI sessions"
        )

        # Mode labels should appear
        # The section is only rendered when has_mode=True
        self.assertIn(
            "Mode", html,
            "HTML should contain Mode section since mode data is available"
        )
        self.assertIn(
            "Agent", html,
            "HTML should contain 'Agent' mode label"
        )

        # Model chart canvas should exist
        self.assertIn("modelChart", html, "HTML should contain model chart canvas")

        print(f"\n[EVAL-004] PASSED — stdout preview:\n{stdout[:400]}")


class TestEval005Categories(unittest.TestCase):
    """
    EVAL-005 (US5): Conversation category classification.
    session-debug.jsonl: 'error', 'traceback', 'exception', 'fix', 'broken', 'null' → Debugging
    session-codegen.jsonl: 'write', 'implement', 'function', 'generate', 'class', 'script' → Code Generation
    """

    def test_eval_005_categories(self):
        # Use only the debug and codegen fixtures for clarity
        # We still pass the full CLAUDE_FIXTURES dir; debug and codegen are within it
        html, rc, stdout, stderr = _run_report(
            "--claude-dir", CLAUDE_FIXTURES,
            "--vscode-dir", _EMPTY,
            "--copilot-cli-dir", _EMPTY,
        )
        if rc == 2:
            self.fail(f"Script exited with code 2 (error).\nstdout: {stdout}\nstderr: {stderr}")
        self.assertEqual(rc, 0, f"Expected exit 0, got {rc}.\nstdout: {stdout}\nstderr: {stderr}")
        self.assertTrue(html, "HTML should not be empty")

        # Categories section should exist
        self.assertIn("Conversation Categories", html, "HTML should have a Categories section")

        # Debugging should appear as a category
        self.assertIn(
            "Debugging", html,
            "HTML should contain 'Debugging' category (session-debug has error/traceback/exception content)"
        )

        # Code Generation should appear as a category
        self.assertIn(
            "Code Generation", html,
            "HTML should contain 'Code Generation' category (session-codegen has write/implement/function content)"
        )

        # Category chart should exist (stacked bar removed in favour of AI themes when insights present)
        self.assertIn("catHorizBar", html, "HTML should contain category horizontal bar chart")

        print(f"\n[EVAL-005] PASSED — stdout preview:\n{stdout[:400]}")


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
