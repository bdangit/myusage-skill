# Contract: .github/workflows/ci.yml

**Type**: GitHub Actions workflow
**Purpose**: Automated validation on PRs and automated release on merge to main.

## Triggers

| Event | Condition | Jobs triggered |
|-------|-----------|---------------|
| `pull_request` | targeting `main` | `validate` only |
| `push` | to `main` | `validate` → `release` (if validate passes) |

## Jobs

### validate

| Property | Value |
|----------|-------|
| Runs on | `ubuntu-24.04` |
| Python | `3.10` (via `actions/setup-python@v5`) |
| Steps | `validate.sh` (single-line invocation) |
| Failure behaviour | Fails the PR check; blocks `release` job |

### release

| Property | Value |
|----------|-------|
| Runs on | `ubuntu-24.04` |
| Needs | `validate` (must pass) |
| Condition | `github.event_name == 'push'` |
| Permissions | `contents: write` |
| Steps | semver validation → version bump → commit `[skip ci]` → tag → GitHub Release |

## Outputs

| Artifact | Description |
|----------|-------------|
| Updated `plugin.json` | Version incremented, committed back to `main` |
| Git tag | `vMAJOR.MINOR.PATCH` pushed to origin |
| GitHub Release | Auto-generated notes from merged PRs since last tag |

## Loop prevention

The version bump commit message contains `[skip ci]`. GitHub Actions natively skips workflow runs for commits with this marker, preventing the release job from re-triggering on its own commit.

## Required repository configuration (post-implementation)

- Branch protection on `main` must require the `validate` status check to pass before merging
- GHA bot must have `contents: write` (enabled via `permissions: contents: write` in workflow — no repo setting change needed for public repos)
