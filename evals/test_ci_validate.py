"""
Evals for .github/scripts/validate.sh

EVAL-001: Syntax error in generate_report.py → non-zero exit, filename in output
EVAL-002: SKILL.md missing name: field → non-zero exit, output identifies missing field
EVAL-003: Clean repo → exit 0, three [OK] lines
EVAL-005: Local run from repo root → exit 0, all three [OK] lines present

Note: All tests that invoke validate.sh are skipped when running inside validate.sh
(VALIDATE_SH_RUNNING=1) to prevent infinite recursion:
validate.sh → evals → test_ci_validate.py → validate.sh → ...
"""

import os
import shutil
import subprocess
import tempfile
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VALIDATE_SH = os.path.join(REPO_ROOT, ".github", "scripts", "validate.sh")

# True when we are already inside a validate.sh invocation
RUNNING_IN_VALIDATE = os.environ.get("VALIDATE_SH_RUNNING") == "1"


def run_validate(env=None, cwd=None):
    """Run validate.sh and return (returncode, combined_output).

    Always clears VALIDATE_SH_RUNNING so the child validate.sh starts fresh,
    ensuring tests that expect failure (EVAL-001/002) are not short-circuited
    by the recursion guard.
    """
    merged_env = os.environ.copy()
    merged_env.pop("VALIDATE_SH_RUNNING", None)
    if env:
        merged_env.update(env)
    result = subprocess.run(
        ["bash", VALIDATE_SH],
        capture_output=True,
        text=True,
        env=merged_env,
        cwd=cwd or REPO_ROOT,
    )
    combined = result.stdout + result.stderr
    return result.returncode, combined


@unittest.skipIf(RUNNING_IN_VALIDATE, "Skipped inside validate.sh to prevent infinite recursion")
class TestCIValidate(unittest.TestCase):

    def test_eval_001_syntax_error_fails(self):
        """EVAL-001: Syntax error in generate_report.py → non-zero exit, filename in output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scripts_dir = os.path.join(tmpdir, "scripts")
            os.makedirs(scripts_dir)
            src = os.path.join(REPO_ROOT, "scripts", "generate_report.py")
            bad_py = os.path.join(scripts_dir, "generate_report.py")
            shutil.copy(src, bad_py)
            with open(bad_py, "a") as f:
                f.write("\ndef broken syntax!!!\n")

            evals_dst = os.path.join(tmpdir, "evals")
            shutil.copytree(os.path.join(REPO_ROOT, "evals"), evals_dst)
            shutil.copy(os.path.join(REPO_ROOT, "SKILL.md"), os.path.join(tmpdir, "SKILL.md"))

            returncode, output = run_validate(cwd=tmpdir)

        self.assertNotEqual(returncode, 0, "Expected non-zero exit on syntax error")
        self.assertIn("generate_report.py", output)

    def test_eval_002_skill_md_missing_name_fails(self):
        """EVAL-002: SKILL.md missing name: field → non-zero exit, output identifies missing field."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("---\ndescription: A description\n---\nContent here\n")
            tmp_skill = f.name

        try:
            returncode, output = run_validate(env={"SKILL_MD": tmp_skill})
        finally:
            os.unlink(tmp_skill)

        self.assertNotEqual(returncode, 0, "Expected non-zero exit when name: is missing")
        self.assertTrue(
            "name" in output.lower() or "frontmatter" in output.lower() or "SKILL" in output,
            f"Expected output to identify missing field, got: {output!r}",
        )

    def test_eval_003_clean_repo_passes(self):
        """EVAL-003: Clean repo → exit 0, output contains three [OK] lines."""
        returncode, output = run_validate()

        self.assertEqual(returncode, 0, f"Expected exit 0 on clean repo.\nOutput:\n{output}")
        ok_lines = [line for line in output.splitlines() if line.startswith("[OK]")]
        self.assertEqual(len(ok_lines), 3, f"Expected 3 [OK] lines, got {len(ok_lines)}: {ok_lines}")

    def test_eval_005_local_run_from_repo_root(self):
        """EVAL-005: Run validate.sh from repo root → exit 0, all three [OK] lines present."""
        returncode, output = run_validate(cwd=REPO_ROOT)

        self.assertEqual(returncode, 0, f"Expected exit 0 running from repo root.\nOutput:\n{output}")
        self.assertIn("[OK] Python syntax check", output)
        self.assertIn("[OK] SKILL.md frontmatter", output)
        self.assertIn("[OK] Evals", output)


if __name__ == "__main__":
    unittest.main()
