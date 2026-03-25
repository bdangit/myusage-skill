"""
Evals for `claude plugin validate .`

EVAL-006: Clean repo → exit 0, "Validation passed" in output
EVAL-007: marketplace.json with unrecognized root key → non-zero exit
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_DIR = os.path.join(REPO_ROOT, ".claude-plugin")

CLAUDE_AVAILABLE = shutil.which("claude") is not None


def run_plugin_validate(cwd=None):
    """Run `claude plugin validate .` and return (returncode, combined_output)."""
    result = subprocess.run(
        ["claude", "plugin", "validate", "."],
        capture_output=True,
        text=True,
        cwd=cwd or REPO_ROOT,
    )
    return result.returncode, result.stdout + result.stderr


@unittest.skipUnless(CLAUDE_AVAILABLE, "claude CLI not found in PATH")
class TestPluginValidate(unittest.TestCase):

    def test_eval_006_clean_repo_passes(self):
        """EVAL-006: `claude plugin validate .` on clean repo → exit 0, Validation passed."""
        returncode, output = run_plugin_validate()

        self.assertEqual(returncode, 0, f"Expected exit 0.\nOutput:\n{output}")
        self.assertIn("Validation passed", output)

    def test_eval_007_bad_marketplace_field_fails(self):
        """EVAL-007: marketplace.json with unrecognized root key → non-zero exit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dst = os.path.join(tmpdir, ".claude-plugin")
            shutil.copytree(PLUGIN_DIR, plugin_dst)

            marketplace = os.path.join(plugin_dst, "marketplace.json")
            with open(marketplace) as f:
                data = json.load(f)
            data["bogus_invalid_field"] = "should_fail"
            with open(marketplace, "w") as f:
                json.dump(data, f, indent=2)

            returncode, output = run_plugin_validate(cwd=tmpdir)

        self.assertNotEqual(returncode, 0, f"Expected non-zero exit on bad field.\nOutput:\n{output}")
        self.assertIn("bogus_invalid_field", output)


if __name__ == "__main__":
    unittest.main()
