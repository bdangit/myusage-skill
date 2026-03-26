# Quickstart: Codex Platform Support

## For users — include Codex in your report

Codex sessions are discovered automatically if `~/.codex/state_N.sqlite` exists.
No extra configuration is needed:

```bash
python skills/myusage/scripts/generate_report.py
```

The report will include a Codex section alongside Claude Code and Copilot when
Codex session data is present on your machine.

---

## For users — point to a custom Codex data directory

```bash
python skills/myusage/scripts/generate_report.py --codex-dir /path/to/codex/data
```

---

## For contributors — run evals locally

```bash
# From repo root — runs all evals including new Codex tests
python -m unittest discover -s evals -p "test_*.py"
```

Or run only the Codex-specific eval tests:

```bash
python -m unittest discover -s evals -p "test_codex*.py"
```

---

## For contributors — validate fixture parsing manually

```python
import sys
sys.path.insert(0, "skills/myusage/scripts")
from generate_report import parse_codex, build_report

sessions = parse_codex("evals/fixtures/codex")
print(f"Parsed {len(sessions)} Codex sessions")
for s in sessions:
    print(f"  {s.session_id[:8]}  model={s.model}  msgs={s.message_count}  tokens={s.input_tokens}")
```

Expected output with the committed fixtures:
```
Parsed 3 Codex sessions
  session-c  model=codex-mini-latest  msgs=2  tokens=1840
  session-c  model=o3                 msgs=3  tokens=3200
  session-c  model=codex-mini-latest  msgs=1  tokens=950
```

---

## Notes on Codex cost display

Codex sessions display `—` in cost columns. The Codex session database provides only a
combined token total (input + output together), making accurate per-token cost estimation
impossible. A footnote in the report explains this limitation.

---

## Implementation branch

All implementation work for this feature goes on branch `004-codex-support-impl`, created
from `main` **after** this spec branch is merged. Per the project constitution, `speckit.implement`
MUST NOT be run on a spec branch.
