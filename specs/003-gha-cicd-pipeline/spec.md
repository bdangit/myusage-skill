# Feature Specification: GHA CI/CD Pipeline

**Feature Branch**: `003-gha-cicd-pipeline`
**Created**: 2026-03-21
**Status**: Draft
**Input**: User description: "we are building a cicd pipeline for the myusage-skill project using GitHub Actions with validate and release jobs, local-runnable scripts, and automatic patch version bumping on merge to main."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - PR Contributor Gets Fast Feedback (Priority: P1)

A contributor opens a pull request against `main`. The pipeline automatically validates the change — checking syntax, SKILL.md structure, and running all eval tests — and reports pass/fail status directly on the PR. If anything fails, the merge is blocked until fixed.

**Why this priority**: This is the core safety net for accepting contributions. Without it, broken code can land on main and corrupt a release.

**Independent Test**: Open a PR with a deliberate syntax error in `scripts/generate_report.py` and verify the validation job fails and blocks merge. Then fix it and verify it passes.

**Acceptance Scenarios**:

1. **Given** a PR is opened with a Python syntax error, **When** the validate job runs, **Then** it fails, reports the error, and the PR cannot be merged.
2. **Given** a PR is opened with valid Python, valid SKILL.md frontmatter, and all evals passing, **When** the validate job runs, **Then** it passes and the PR is unblocked.
3. **Given** a PR is opened with a SKILL.md missing the `name` field, **When** the validate job runs, **Then** it fails with a descriptive frontmatter error.
4. **Given** a PR is opened where one or more eval tests fail, **When** the validate job runs, **Then** it fails and reports which tests failed.

---

### User Story 2 - Merge to Main Produces a Tagged Release (Priority: P1)

A maintainer merges a PR into `main`. The pipeline first re-runs validation, then — if validation passes — automatically bumps the patch version in `plugin.json`, commits the bump, creates a git tag, and publishes a GitHub Release with auto-generated release notes.

**Why this priority**: Releases must be automated and consistent. Manual tagging is error-prone and slows down contribution velocity.

**Independent Test**: Merge a clean PR to main with `plugin.json` at version `1.0.1` and verify that `plugin.json` is updated to `1.0.2`, a `v1.0.2` tag exists, and a GitHub Release for `v1.0.2` is published — all without manual intervention.

**Acceptance Scenarios**:

1. **Given** a merge to main where validation passes and `plugin.json` version is `1.0.1`, **When** the release job runs, **Then** `plugin.json` is updated to `1.0.2`, a commit is pushed with `[skip ci]`, a `v1.0.2` tag is created, and a GitHub Release is published.
2. **Given** a merge to main where validation fails, **When** the release job is evaluated, **Then** it does not run — no version bump, no tag, no release.
3. **Given** a merge to main contains a `feat:` commit and `plugin.json` is at `1.0.5`, **When** the release job runs, **Then** `plugin.json` is updated to `1.1.0` (minor bump, patch reset to 0).
4. **Given** the release job pushes a version bump commit, **When** that commit lands on main, **Then** the pipeline does NOT trigger another release (loop prevention via `[skip ci]`).

---

### User Story 3 - Developer Validates Locally Before Pushing (Priority: P2)

A developer wants to run the same checks locally that CI will run, before opening a PR. They invoke a single script (`.github/scripts/validate.sh`) and get the same pass/fail result as the pipeline.

**Why this priority**: Local reproducibility reduces wasted CI cycles and speeds up contributor iteration. It's a quality-of-life requirement, not a safety requirement.

**Independent Test**: Run `.github/scripts/validate.sh` on a clean checkout and verify it exits 0. Introduce a syntax error and verify it exits non-zero with a clear error message.

**Acceptance Scenarios**:

1. **Given** a developer runs `.github/scripts/validate.sh` locally with all checks passing, **When** it completes, **Then** exit code is 0 and output confirms each check passed.
2. **Given** a developer runs `.github/scripts/validate.sh` locally with a failing eval, **When** it completes, **Then** exit code is non-zero and the failing test is identified.

---

### Edge Cases

- What happens when the version bump commit itself triggers the pipeline? → Prevented by `[skip ci]` in the commit message.
- What happens if `plugin.json` has a malformed version string (e.g., `"1.0"` instead of `"1.0.1"`)? → Validation should catch this and fail the release job before tagging.
- What happens if a git tag for the bumped version already exists? → Release job should fail with a clear conflict error rather than silently overwriting.
- What happens if evals pass locally but fail in CI due to environment differences? → CI uses the same Python stdlib-only constraint; no external dependencies to diverge.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The pipeline MUST run the validate job on every pull request targeting `main`.
- **FR-002**: The pipeline MUST run the validate job on every push to `main` before the release job begins.
- **FR-003**: The validate job MUST check Python syntax for `scripts/generate_report.py` and fail immediately on any syntax error.
- **FR-004**: The validate job MUST verify that `SKILL.md` contains a valid frontmatter block with both `name` and `description` fields present.
- **FR-005**: The validate job MUST run all eval tests and fail if any test fails.
- **FR-006**: The release job MUST only execute after the validate job passes; it MUST NOT run on pull request events.
- **FR-007**: The release job MUST determine the version bump level from commit messages since the last tag: any commit with `!` in the type/scope (e.g., `feat!:`, `fix!:`) OR `BREAKING CHANGE:` in the body triggers a **major** bump; `feat:` triggers **minor**; `fix:` triggers **patch**; no match defaults to **patch**. Always increment forward — no rollbacks or re-releases of prior versions.
- **FR-008**: The release job MUST commit the updated `plugin.json` with a message containing `[skip ci]` to prevent pipeline loops.
- **FR-009**: The release job MUST create and push a git tag matching the new version (e.g., `v1.0.2`).
- **FR-010**: The release job MUST create a GitHub Release for the new tag with auto-generated release notes.
- **FR-011**: All validation steps MUST be executable locally via a single command: `.github/scripts/validate.sh`.
- **FR-012**: The `version` field MUST be removed from `.claude-plugin/marketplace.json`; `.claude-plugin/plugin.json` is the sole version source.
- **FR-013**: Version bump level MUST be determined automatically from conventional commit messages — no manual edits to `plugin.json` are required for any bump level.
- **FR-014**: The release job MUST validate that `.claude-plugin/plugin.json` is valid JSON with a strict `MAJOR.MINOR.PATCH` semver version field before bumping. It MUST also validate that `.claude-plugin/marketplace.json` is valid JSON. Either failure MUST abort the release with a clear error.

### Key Entities

- **plugin.json**: The single source of truth for the skill version. Located at `.claude-plugin/plugin.json`. The `version` field follows semver (`MAJOR.MINOR.PATCH`).
- **validate job**: The CI gate that runs on both PRs and pushes to main. Covers syntax, SKILL.md structure, and evals.
- **release job**: Runs only on pushes to main after validate passes. Owns version bump, tagging, and GitHub Release creation.
- **.github/scripts/validate.sh**: Shell script wrapping all validate job steps for local execution.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every PR to main triggers the validate job within 60 seconds of the PR being opened or updated.
- **SC-002**: A failed validate check blocks 100% of PRs from merging — no broken code reaches main.
- **SC-003**: Every merge to main that passes validation produces a published GitHub Release automatically, with no manual steps required.
- **SC-004**: A contributor can replicate the full CI validation locally with a single command and get the same pass/fail result as the pipeline.
- **SC-005**: The version in `plugin.json` is the only file that needs to change for a release — no manual sync to other files.
- **SC-006**: The release pipeline completes (validate + version bump + tag + publish) within 3 minutes of a merge to main.

### Eval Requirements *(mandatory — per constitution)*

- **EVAL-001 (US1)**: Given a branch with a syntax error introduced into `scripts/generate_report.py`, when `.github/scripts/validate.sh` is run, then exit code is non-zero and the output identifies the syntax error.
- **EVAL-002 (US1)**: Given a branch where `SKILL.md` frontmatter is missing the `name` field, when `.github/scripts/validate.sh` is run, then exit code is non-zero and the output identifies the missing field.
- **EVAL-003 (US1)**: Given a clean branch where all checks pass, when `.github/scripts/validate.sh` is run, then exit code is 0 and all check steps report success.
- **EVAL-004 (US2)**: Given `plugin.json` at version `X.Y.Z`, the release script MUST produce: `X.Y.(Z+1)` for a `fix:` commit, `X.(Y+1).0` for a `feat:` commit, and `(X+1).0.0` for a `BREAKING CHANGE:` commit — in all cases the result is valid semver.
- **EVAL-005 (US3)**: Given a developer runs `.github/scripts/validate.sh` locally on a clean checkout, when it completes, then exit code is 0 and output matches what CI would produce.
- **EVAL-006 (US2)**: Given `plugin.json` has a malformed version (e.g., `"1.0"` or `"v1.0.1"`), when the release job runs, then it aborts before tagging and outputs a clear semver validation error.
- **EVAL-007 (US2)**: Given `marketplace.json` is invalid JSON, when the release job runs, then it aborts before tagging and outputs a clear parse error.

## Assumptions

- The project uses pinned GHA runners (`ubuntu-24.04`) for reproducible, secure releases — not `ubuntu-latest` which can change over time.
- Python 3.10 is explicitly selected in CI via `actions/setup-python` and is the version used for local `.github/scripts/validate.sh` runs.
- Branch protection on `main` requiring the validate status check to pass will be configured once the workflow file exists — SC-002 depends on this.
- The GHA bot has `contents: write` permission for pushing the version bump commit and creating releases.
- `softprops/action-gh-release` is used for GitHub Release creation (widely adopted, stable).
- `.github/scripts/validate.sh` does not need to replicate the git operations from the release job — only the validation steps.
- Releases always move forward — no rollbacks, re-releases, or re-tagging of prior versions.
