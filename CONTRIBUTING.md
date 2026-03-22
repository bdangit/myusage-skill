# Contributing to myusage-skill

This guide is for humans and AI agents alike. Follow it to keep the release process clean and predictable.

## Commit Message Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/). Every commit message must follow this format:

```
<type>(<scope>): <short description>
```

### Types that trigger a version bump

| Type | When to use | Bump |
|------|-------------|------|
| `feat:` | New capability added to the skill | Minor (`1.0.0` → `1.1.0`) |
| `fix:` | Bug fix in the skill | Patch (`1.0.0` → `1.0.1`) |
| `feat!:` or `fix!:` | Breaking change in skill behavior | Major (`1.0.0` → `2.0.0`) |

A commit body containing `BREAKING CHANGE:` also triggers a major bump.

### Types that do NOT trigger a version bump

| Type | When to use |
|------|-------------|
| `docs:` | Spec, plan, README, or any documentation change |
| `chore:` | Maintenance, config, tooling |
| `ci:` | CI/CD workflow changes (`.github/`) |
| `test:` | Eval or test changes only |
| `refactor:` | Code restructuring with no behavior change |
| `style:` | Formatting, whitespace |

**Rule**: Only changes that affect what the skill does for the user should use `feat:` or `fix:`. Spec work, planning artifacts, CI changes, and documentation always use a non-bumping type.

### Examples

```bash
# Skill changes — will trigger a release
feat: add session heatmap to usage report
fix: handle missing copilot session directory gracefully
feat!: change report output path from /tmp to user-specified flag

# Non-skill changes — will NOT trigger a release
docs(003): add plan and tasks for CI/CD pipeline
ci: add validate job to GitHub Actions workflow
chore: remove version field from marketplace.json
test: add eval for malformed plugin.json version
refactor: extract session parser into helper function
```

---

## Branch Naming

| Branch type | Pattern | Example |
|-------------|---------|---------|
| Spec/planning | `NNN-feature-name` | `003-gha-cicd-pipeline` |
| Implementation | `NNN-feature-name-impl` | `003-gha-cicd-pipeline-impl` |
| Bug fix | `fix/short-description` | `fix/missing-copilot-sessions` |

Spec branches contain **docs only** — no `.py`, `.sh`, or other implementation files.
Implementation branches contain **code only** — branched from `main` after the spec branch is merged.

---

## Local Validation

Before opening a PR, run the validation script from the repo root:

```bash
.github/scripts/validate.sh
```

This runs the same checks as the CI validate job:
- Python syntax check
- `SKILL.md` frontmatter validation
- Full eval suite

Exit 0 = ready to push. Non-zero = fix before opening a PR.

---

## Pull Request Process

1. Branch from `main`
2. Make your changes with properly prefixed commits
3. Run `.github/scripts/validate.sh` locally
4. Open a PR targeting `main`
5. The `validate` CI job runs automatically — it must pass before merge
6. For skill changes (`feat:`/`fix:`), release-please will open a Release PR after your PR merges — merge it when ready to publish

---

## Release Process (maintainers)

Releases are fully automated. You do not need to manually bump versions or create tags.

1. Merge a PR with `feat:` or `fix:` commits to `main`
2. release-please opens a Release PR (e.g., `chore: release 1.1.0`)
3. The Release PR shows the version bump and auto-generated changelog
4. Merge the Release PR — the tag and GitHub Release are created automatically

For major version bumps, use `feat!:` or include `BREAKING CHANGE:` in the commit body.
For minor/patch, just use `feat:` or `fix:` — release-please determines the level automatically.

---

## For AI Agents

When generating commit messages in this repo:

- Use `docs:` for any spec, plan, tasks, or markdown-only changes
- Use `ci:` for changes under `.github/`
- Use `feat:` or `fix:` **only** when `scripts/generate_report.py` or `SKILL.md` behavior changes
- Never use `feat:` or `fix:` for planning artifacts, even if the planning is for a new feature
- The scope (e.g., `feat(003):`) is optional but helpful for traceability on feature branches
