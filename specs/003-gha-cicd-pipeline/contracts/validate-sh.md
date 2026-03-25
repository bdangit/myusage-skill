# Contract: .github/scripts/validate.sh

**Type**: Local-runnable shell script
**Purpose**: Runs all CI validation checks locally, producing the same pass/fail result as the GHA validate job.

## Usage

```bash
# From repo root
.github/scripts/validate.sh
```

No arguments. No environment variables required. Must be run from the repo root.

## Checks (in order)

| Step | Command | Failure condition |
|------|---------|------------------|
| Python syntax | `python3 -m py_compile scripts/generate_report.py` | Non-zero exit |
| SKILL.md frontmatter | inline check for `---` block with `name:` and `description:` | Missing block or fields |
| Evals | `python3 -m unittest discover -s evals -p "test_*.py"` | Any test fails |

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | All checks passed |
| `1` | One or more checks failed (first failure stops execution via `set -e`) |

## Output format

Each passing step prints a single line:
```
[OK] Python syntax check
[OK] SKILL.md frontmatter
[OK] Evals (N tests passed)
```

On failure, the failing command's output is shown directly, followed by a non-zero exit.

## Requirements

- `python3` must be available on `$PATH` (Python 3.10+)
- Must be run from repo root (relative paths assumed)
- Script must be executable: `chmod +x .github/scripts/validate.sh`
