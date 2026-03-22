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
if ! grep -q "^---" "$SKILL_MD"; then
  echo "ERROR: $SKILL_MD missing frontmatter (no --- block found)" >&2
  exit 1
fi
if ! awk '/^---/{found++} found==1 && /name:/{name=1} found==1 && /description:/{desc=1} found==2{exit} END{exit !(name && desc)}' "$SKILL_MD"; then
  echo "ERROR: $SKILL_MD frontmatter missing required 'name:' or 'description:' field" >&2
  exit 1
fi
echo "[OK] SKILL.md frontmatter"

# Step 3: Run evals
output=$(python3 -m unittest discover -s evals -p "test_*.py" -v 2>&1)
ran=$(echo "$output" | grep "^Ran " | head -1)
n=$(echo "$ran" | grep -oE '[0-9]+' | head -1)
echo "[OK] Evals (${n:-?} tests passed)"
