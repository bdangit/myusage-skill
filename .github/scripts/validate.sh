#!/usr/bin/env bash
set -e

# Guard against recursive invocation (test_ci_validate.py calls validate.sh,
# which runs the eval suite, which would call validate.sh again).
export VALIDATE_SH_RUNNING=1

SKILL_MD="${SKILL_MD:-./SKILL.md}"

# Step 1: Python syntax check
python3 -m py_compile scripts/generate_report.py
echo "[OK] Python syntax check"

# Step 2: SKILL.md frontmatter check
if [ ! -r "$SKILL_MD" ]; then
  echo "ERROR: $SKILL_MD does not exist or is not readable" >&2
  exit 1
fi
if ! awk 'NF { print; exit }' "$SKILL_MD" | grep -qE '^---[[:space:]]*$'; then
  echo "ERROR: $SKILL_MD frontmatter must start with --- as first non-empty line" >&2
  exit 1
fi
if ! awk '/^---[[:space:]]*$/{found++} found==1 && /^[[:space:]]*name:[[:space:]]/{name=1} found==1 && /^[[:space:]]*description:[[:space:]]/{desc=1} found==2{exit} END{exit !(found>1 && name && desc)}' "$SKILL_MD"; then
  echo "ERROR: $SKILL_MD frontmatter missing required 'name:' or 'description:' field" >&2
  exit 1
fi
echo "[OK] SKILL.md frontmatter"

# Step 3: Run evals
set +e
output=$(python3 -m unittest discover -s evals -p "test_*.py" -v 2>&1)
status=$?
set -e

if [ "$status" -ne 0 ]; then
  echo "$output"
  echo "ERROR: Evals failed (unittest exited with status $status)" >&2
  exit "$status"
fi

ran=$(echo "$output" | grep "^Ran " | head -1)
n=$(echo "$ran" | grep -oE '[0-9]+' | head -1)

if [ -z "$n" ] || [ "$n" -eq 0 ]; then
  echo "$output"
  echo "ERROR: Evals ran 0 tests or could not determine test count" >&2
  exit 1
fi

echo "[OK] Evals (${n} tests passed)"
