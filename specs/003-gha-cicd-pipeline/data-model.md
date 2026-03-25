# Data Model: GHA CI/CD Pipeline

**Feature**: 003-gha-cicd-pipeline
**Date**: 2026-03-21

---

## plugin.json

Single source of truth for the skill version.

```json
{
  "name": "myusage",
  "version": "MAJOR.MINOR.PATCH",
  "description": "...",
  "author": { "name": "..." },
  "repository": "...",
  "license": "MIT",
  "skills": ["./SKILL.md"],
  "platforms": ["macos"],
  "requirements": { "python": ">=3.10" }
}
```

**Validation rules**:
- `version` MUST match `^\d+\.\d+\.\d+$` (strict semver, no `v` prefix, no pre-release suffix)
- File MUST be valid JSON
- Validated by the release job before any bump or tag is created

**Mutation**: Release job reads `version`, computes new version, writes back. No other fields are touched.

---

## marketplace.json

Discovery/catalog file. Points to the plugin source. Does not own version.

```json
{
  "name": "myusage-skill",
  "description": "...",
  "owner": { "name": "bdangit" },
  "plugins": [
    {
      "name": "myusage",
      "source": "./",
      "description": "...",
      "skills": ["./"],
      "author": { "name": "bdangit" },
      "repository": "...",
      "license": "MIT",
      "tags": ["..."]
    }
  ]
}
```

**Change from current state**: `version` field removed from the plugin entry.
**Validation rules**: File MUST be valid JSON. Validated by release job before tagging.
**Mutation**: None at runtime. The `version` field is removed once during implementation.

---

## Version Bump Algorithm

```
inputs:
  current_version: str  — read from plugin.json (e.g. "1.0.1")
  commits: list[str]    — git log subjects + bodies since last tag

steps:
  1. validate current_version matches ^\d+\.\d+\.\d+$
  2. parse MAJOR, MINOR, PATCH = map(int, current_version.split("."))
  3. determine bump_level:
       if any commit subject matches breaking pattern OR body contains "BREAKING CHANGE:"
           → bump_level = MAJOR
       elif any commit subject starts with "feat:"
           → bump_level = MINOR
       else
           → bump_level = PATCH  (covers "fix:" and no-match default)
  4. compute new_version:
       MAJOR bump → (MAJOR+1).0.0
       MINOR bump → MAJOR.(MINOR+1).0
       PATCH bump → MAJOR.MINOR.(PATCH+1)

output:
  new_version: str  (e.g. "1.0.2")
```

**Breaking change patterns** (checked against commit subject):
```
^(feat|fix|chore|refactor|perf|docs|style|test|build|ci)(\([^)]+\))?!:
```

---

## Git Tag

Format: `v{MAJOR}.{MINOR}.{PATCH}` (e.g., `v1.0.2`)

Created by the release job after `plugin.json` is updated and committed. Tags are never deleted or moved — releases always move forward.

---

## validate.sh Exit Contract

| Condition | Exit Code | Stdout |
|-----------|-----------|--------|
| All checks pass | `0` | Per-check "OK" lines |
| Python syntax error | `1` | Error from `py_compile` |
| SKILL.md frontmatter invalid | `1` | Descriptive error message |
| Any eval test fails | `1` | unittest failure output |
