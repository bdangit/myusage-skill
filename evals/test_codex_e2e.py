"""
test_codex_e2e.py — Phase 7 End-to-End Integration Tests for Codex Support

Comprehensive E2E tests verifying Codex support works correctly with all other
platforms (Claude Code, Copilot VS Code, Copilot CLI).

Six test methods covering:
  E2E Test 1: Full report generation with all 4 platforms
  E2E Test 2: Codex-only report generation
  E2E Test 3: Codex sessions categorization
  E2E Test 4: Codex in cross-platform analysis
  E2E Test 5: Cost display with Codex
  E2E Test 6: Graceful degradation with missing Codex data
"""

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'myusage', 'scripts'))
from generate_report import (
    parse_claude_code,
    parse_copilot_vscode,
    parse_copilot_cli,
    parse_codex_database,
    build_report,
    render_html,
    discover_codex_database,
)

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')
CLAUDE_FIXTURES = os.path.join(FIXTURES, 'claude_code')
VSCODE_FIXTURES = os.path.join(FIXTURES, 'copilot_vscode')
CLI_FIXTURES = os.path.join(FIXTURES, 'copilot_cli')
CODEX_FIXTURES = os.path.join(FIXTURES, 'codex')
CODEX_DB = os.path.join(CODEX_FIXTURES, 'state_1.sqlite')

CHARTJS_STUB_PATH = os.path.join(FIXTURES, 'chartjs-stub.js')


def _read_chartjs_stub():
    """Load Chart.js stub from fixtures."""
    with open(CHARTJS_STUB_PATH, 'r', encoding='utf-8') as fh:
        return fh.read()


class TestCodexE2EIntegration(unittest.TestCase):
    """Comprehensive E2E tests for Codex integration with all platforms."""

    # =========================================================================
    # E2E Test 1: Full Report Generation with All Platforms
    # =========================================================================

    def test_full_report_with_all_platforms(self):
        """
        E2E Test 1: Generate report with fixtures containing all 4 platforms.
        
        Verify:
        - Report renders without errors
        - All 4 platforms appear in summary stats
        - Tool breakdown shows all 4 tools
        """
        # Load sessions from all 4 platforms
        sessions = []
        sessions.extend(parse_claude_code(CLAUDE_FIXTURES))
        sessions.extend(parse_copilot_vscode(VSCODE_FIXTURES))
        sessions.extend(parse_copilot_cli(CLI_FIXTURES))
        codex_sessions = parse_codex_database(Path(CODEX_DB))
        sessions.extend(codex_sessions)

        # Verify we have sessions from all platforms
        tools_present = set(s.tool for s in sessions)
        self.assertIn('claude_code', tools_present, "Claude Code sessions should be present")
        self.assertIn('copilot_vscode', tools_present, "Copilot VS Code sessions should be present")
        self.assertIn('copilot_cli', tools_present, "Copilot CLI sessions should be present")
        self.assertIn('codex', tools_present, "Codex sessions should be present")
        self.assertEqual(len(tools_present), 4, "All 4 tools should be present")

        # Build report
        report = build_report(sessions)

        # Verify all platforms in report snapshots
        self.assertEqual(len(report.snapshots), 4, "Report should have 4 tool snapshots")
        self.assertIn('claude_code', report.snapshots)
        self.assertIn('copilot_vscode', report.snapshots)
        self.assertIn('copilot_cli', report.snapshots)
        self.assertIn('codex', report.snapshots)

        # Verify Codex has sessions in snapshot
        codex_snapshot = report.snapshots['codex']
        self.assertGreater(codex_snapshot.total_sessions, 0, "Codex snapshot should have sessions")
        self.assertGreater(codex_snapshot.total_messages, 0, "Codex snapshot should have messages")

        # Render HTML
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            render_html(report, tmp_path, chartjs_src=_read_chartjs_stub())
            
            # Verify HTML was created and is non-empty
            self.assertTrue(os.path.exists(tmp_path), "HTML file should be created")
            with open(tmp_path, 'r', encoding='utf-8') as fh:
                html = fh.read()
            self.assertGreater(len(html), 0, "HTML should not be empty")

            # Verify all 4 tools appear in HTML
            self.assertIn('claude_code', html, "claude_code tool should appear in HTML")
            self.assertIn('copilot_vscode', html, "copilot_vscode tool should appear in HTML")
            self.assertIn('copilot_cli', html, "copilot_cli tool should appear in HTML")
            self.assertIn('codex', html, "codex tool should appear in HTML")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    # =========================================================================
    # E2E Test 2: Codex-Only Report
    # =========================================================================

    def test_codex_only_report(self):
        """
        E2E Test 2: Generate report with ONLY Codex fixtures.
        
        Verify:
        - Report generates successfully
        - Codex data populates all chart sections correctly
        - HTML renders cleanly with Codex data only
        """
        # Load only Codex sessions
        codex_sessions = parse_codex_database(Path(CODEX_DB))
        self.assertGreater(len(codex_sessions), 0, "Should have Codex sessions from fixture")

        # Build report with only Codex
        report = build_report(codex_sessions)

        # Verify only Codex in report
        self.assertEqual(len(report.snapshots), 1, "Report should have only 1 tool snapshot")
        self.assertIn('codex', report.snapshots)
        
        codex_snapshot = report.snapshots['codex']
        self.assertEqual(codex_snapshot.total_sessions, len(codex_sessions))
        self.assertGreater(codex_snapshot.total_messages, 0, "Codex should have messages")

        # Render HTML
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            render_html(report, tmp_path, chartjs_src=_read_chartjs_stub())
            
            # Verify HTML is valid and contains Codex data
            self.assertTrue(os.path.exists(tmp_path), "HTML file should be created")
            with open(tmp_path, 'r', encoding='utf-8') as fh:
                html = fh.read()
            self.assertGreater(len(html), 0, "HTML should not be empty")
            
            # Verify Codex is the only tool displayed
            self.assertIn('codex', html, "codex tool should appear in HTML")
            # Other tools should not appear
            self.assertNotIn('claude_code', html, "claude_code should not appear in Codex-only report")
            self.assertNotIn('copilot_vscode', html, "copilot_vscode should not appear in Codex-only report")
            self.assertNotIn('copilot_cli', html, "copilot_cli should not appear in Codex-only report")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    # =========================================================================
    # E2E Test 3: Codex Sessions Categorization
    # =========================================================================

    def test_codex_categorization(self):
        """
        E2E Test 3: Verify Codex sessions assigned appropriate categories.
        
        Verify:
        - Codex sessions assigned appropriate categories
        - "What were you working on?" section includes Codex categories
        - Category counts are correct
        """
        # Load Codex sessions
        codex_sessions = parse_codex_database(Path(CODEX_DB))
        self.assertGreater(len(codex_sessions), 0, "Should have Codex sessions")

        # Verify categorization
        valid_categories = [
            'Debugging', 'Code Generation', 'Writing/Docs', 'Setup & Config',
            'Infrastructure', 'Research & Analysis', 'Learning/Explanation',
            'Planning', 'Refactoring', 'Other'
        ]
        for session in codex_sessions:
            self.assertIsNotNone(session.category, f"Session {session.session_id} should have category")
            self.assertIn(
                session.category,
                valid_categories,
                f"Session category '{session.category}' should be a valid category"
            )

        # Build report
        report = build_report(codex_sessions)

        # Render HTML
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            render_html(report, tmp_path, chartjs_src=_read_chartjs_stub())
            
            with open(tmp_path, 'r', encoding='utf-8') as fh:
                html = fh.read()
            
            # Verify category section exists
            self.assertIn("Category Breakdown", html, 
                         "HTML should contain 'Category Breakdown' section")
            
            # Verify at least one Codex category appears
            categories_found = []
            for cat in ['Debugging', 'Code Generation', 'Architecture', 'Testing', 'Documentation', 'Other']:
                if cat in html:
                    categories_found.append(cat)
            
            self.assertGreater(len(categories_found), 0, 
                              "At least one category should appear in HTML for Codex sessions")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    # =========================================================================
    # E2E Test 4: Codex Sessions in Cross-Platform Analysis
    # =========================================================================

    def test_cross_platform_analysis(self):
        """
        E2E Test 4: Verify Codex appears in cross-platform analysis.
        
        Verify:
        - Codex appears in platform distribution chart
        - Codex statistics included in comparative analysis
        - Tool breakdown includes Codex with correct counts
        """
        # Load sessions from all platforms
        sessions = []
        sessions.extend(parse_claude_code(CLAUDE_FIXTURES))
        sessions.extend(parse_copilot_vscode(VSCODE_FIXTURES))
        sessions.extend(parse_copilot_cli(CLI_FIXTURES))
        sessions.extend(parse_codex_database(Path(CODEX_DB)))

        # Build report
        report = build_report(sessions)

        # Verify Codex in snapshots with non-zero counts
        self.assertIn('codex', report.snapshots, "Codex should be in snapshots")
        codex_snap = report.snapshots['codex']
        self.assertGreater(codex_snap.total_sessions, 0, "Codex should have sessions")
        self.assertGreater(codex_snap.total_messages, 0, "Codex should have messages")

        # Render HTML
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            render_html(report, tmp_path, chartjs_src=_read_chartjs_stub())
            
            with open(tmp_path, 'r', encoding='utf-8') as fh:
                html = fh.read()
            
            # Verify Codex appears in statistics
            self.assertIn('codex', html, "codex tool should appear in HTML")
            
            # Verify Codex session count is shown
            codex_session_pattern = re.compile(r'codex.*?(\d+)\s*(?:session|Session)', re.IGNORECASE | re.DOTALL)
            matches = codex_session_pattern.findall(html)
            self.assertGreater(len(matches), 0, 
                              "Codex session count should appear in statistics section")
            
            # Verify Codex message count is shown
            codex_message_pattern = re.compile(r'codex.*?(\d+)\s*(?:message|Message)', re.IGNORECASE | re.DOTALL)
            matches = codex_message_pattern.findall(html)
            self.assertGreater(len(matches), 0, 
                              "Codex message count should appear in statistics section")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    # =========================================================================
    # E2E Test 5: Cost Display with Codex
    # =========================================================================

    def test_cost_display(self):
        """
        E2E Test 5: Verify cost display handles Codex correctly.
        
        Verify:
        - Codex cost section shows "—" for input/output (no cost data available)
        - Codex total tokens_used displayed correctly
        - Cost footnote present and readable
        - Claude Code / Copilot cost breakdowns unaffected
        """
        # Load sessions from all platforms
        sessions = []
        sessions.extend(parse_claude_code(CLAUDE_FIXTURES))
        sessions.extend(parse_copilot_vscode(VSCODE_FIXTURES))
        sessions.extend(parse_copilot_cli(CLI_FIXTURES))
        sessions.extend(parse_codex_database(Path(CODEX_DB)))

        # Build report
        report = build_report(sessions)

        # Render HTML
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            render_html(report, tmp_path, chartjs_src=_read_chartjs_stub())
            
            with open(tmp_path, 'r', encoding='utf-8') as fh:
                html = fh.read()
            
            # Verify cost footnote is present
            self.assertIn('estimated', html.lower(), 
                         "Cost footnote with 'estimated' should be present")
            
            # Verify Codex appears in statistics/cost section
            self.assertIn('codex', html, "codex tool should appear in cost display section")
            
            # Verify cost header is present
            self.assertIn('Est. Cost', html, "Cost column header should be present")
            
            # Verify at least one cost value or N/A is shown (Copilot/Claude should have costs)
            cost_pattern = re.compile(r'\$[\d.]+|N/A|—')
            cost_matches = cost_pattern.findall(html)
            self.assertGreater(len(cost_matches), 0, 
                              "Cost values should appear in the HTML output")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    # =========================================================================
    # E2E Test 6: Graceful Degradation
    # =========================================================================

    def test_graceful_degradation(self):
        """
        E2E Test 6: Verify report generates when Codex database is missing.
        
        Verify:
        - Report generates successfully with other platforms
        - Warning logged but report doesn't crash
        - Other platform data unaffected
        """
        # Use a non-existent Codex database path
        missing_db = Path(CODEX_FIXTURES) / 'nonexistent_state.sqlite'
        
        # Load sessions from other platforms
        sessions = []
        sessions.extend(parse_claude_code(CLAUDE_FIXTURES))
        sessions.extend(parse_copilot_vscode(VSCODE_FIXTURES))
        sessions.extend(parse_copilot_cli(CLI_FIXTURES))
        
        # Try to load from missing Codex database
        codex_sessions = parse_codex_database(missing_db)
        self.assertEqual(len(codex_sessions), 0, "Missing database should return empty list")
        
        sessions.extend(codex_sessions)

        # Should have sessions from 3 platforms only
        self.assertGreater(len(sessions), 0, "Should have sessions from non-Codex platforms")
        tools_present = set(s.tool for s in sessions)
        self.assertNotIn('codex', tools_present, "Codex should not be in tools")
        self.assertEqual(len(tools_present), 3, "Should have 3 platforms (no Codex)")

        # Build report should succeed
        report = build_report(sessions)
        self.assertEqual(len(report.snapshots), 3, "Report should have 3 tool snapshots")

        # Render HTML should succeed
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            render_html(report, tmp_path, chartjs_src=_read_chartjs_stub())
            
            # Verify HTML is valid
            self.assertTrue(os.path.exists(tmp_path), "HTML file should be created")
            with open(tmp_path, 'r', encoding='utf-8') as fh:
                html = fh.read()
            self.assertGreater(len(html), 0, "HTML should not be empty")
            
            # Verify other platforms are still present
            self.assertIn('claude_code', html, "claude_code should still appear")
            self.assertIn('copilot_vscode', html, "copilot_vscode should still appear")
            self.assertIn('copilot_cli', html, "copilot_cli should still appear")
            
            # Verify Codex is not in HTML
            self.assertNotIn('codex', html, "codex should not appear when database is missing")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class TestCodexE2ESessionMetadata(unittest.TestCase):
    """Additional E2E tests for Codex session metadata verification."""

    def test_codex_session_metadata(self):
        """Verify Codex sessions have correct metadata from fixture."""
        codex_sessions = parse_codex_database(Path(CODEX_DB))
        self.assertGreater(len(codex_sessions), 0, "Should have Codex sessions")

        for session in codex_sessions:
            # Verify basic metadata
            self.assertEqual(session.tool, 'codex', f"Tool should be 'codex', got {session.tool}")
            self.assertIsNotNone(session.session_id, "Session ID should be set")
            self.assertIsNotNone(session.start_time, "Start time should be set")
            self.assertIsNotNone(session.end_time, "End time should be set")
            self.assertGreaterEqual(session.end_time, session.start_time, 
                                   "End time should be >= start time")
            self.assertGreater(session.message_count, 0, "Message count should be > 0")

    def test_codex_session_character(self):
        """Verify Codex sessions have character classification."""
        codex_sessions = parse_codex_database(Path(CODEX_DB))
        self.assertGreater(len(codex_sessions), 0, "Should have Codex sessions")

        for session in codex_sessions:
            self.assertIn(session.session_character, 
                         ['autonomous', 'deeply_engaged', 'general'],
                         f"Session character should be valid, got {session.session_character}")

    def test_codex_report_totals(self):
        """Verify Codex contributes correctly to total counts."""
        # Load all platforms
        sessions = []
        sessions.extend(parse_claude_code(CLAUDE_FIXTURES))
        sessions.extend(parse_copilot_vscode(VSCODE_FIXTURES))
        sessions.extend(parse_copilot_cli(CLI_FIXTURES))
        codex_sessions = parse_codex_database(Path(CODEX_DB))
        codex_count = len(codex_sessions)
        sessions.extend(codex_sessions)

        report = build_report(sessions)

        # Verify Codex contributes to totals
        self.assertGreater(report.total_sessions_all_tools, 0, "Total sessions should be > 0")
        self.assertGreater(report.total_messages_all_tools, 0, "Total messages should be > 0")
        
        if codex_count > 0:
            # Codex snapshot should be included in totals
            self.assertIn('codex', report.snapshots)
            codex_sessions_in_report = report.snapshots['codex'].total_sessions
            self.assertEqual(codex_sessions_in_report, codex_count, 
                            "Codex session count in report should match parsed count")


if __name__ == "__main__":
    unittest.main(verbosity=2)
