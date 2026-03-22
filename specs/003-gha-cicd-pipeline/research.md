# Research: GHA CI/CD Pipeline

**Feature**: 003-gha-cicd-pipeline
**Date**: 2026-03-21

---

## Decision 1: Script language for validate.sh

**Decision**: Bash
**Rationale**: All validation steps (py_compile, unittest discover, grep for frontmatter) are single-line shell commands. Bash is available everywhere — GHA ubuntu-24.04 and local macOS/Linux. No interpreter setup needed.
**Alternatives considered**: Python — rejected; adds a bootstrap step and is heavier than needed for sequential shell commands.

---

## Decision 2: Release lifecycle management

**Decision**: `googleapis/release-please-action@v4`
**Rationale**: release-please handles the entire release lifecycle — parsing conventional commits, determining semver bump level, opening a Release PR that updates `plugin.json` via jsonpath config, creating the git tag, and publishing the GitHub Release. No custom Python or bash needed for any of this. Maintained by Google, widely adopted across open source projects.

The two-step flow (merge feature PR → release PR opened → merge release PR → tagged release) is a feature, not a drawback: it provides one natural review gate before a version is published.

Config required:
- `release-please-config.json`: `release-type: simple`, extra-files entry pointing `$.version` in `plugin.json`
- `.release-please-manifest.json`: tracks current version, kept in sync with `plugin.json`

**Alternatives considered**:
- Custom `bump_version.py` (Python stdlib) — rejected; reinvents well-solved problem, adds maintenance burden, requires custom semver parsing and git log inspection
- `mathieudutour/github-tag-action` — viable, minimal config, but does not update `plugin.json` automatically (requires an extra step to sync version file)
- `semantic-release` — rejected; Node.js/npm-centric, heavyweight, designed for npm ecosystems
- `softprops/action-gh-release` alone — still requires custom bump logic; rejected for same reason as custom Python

---

## Decision 3: GHA action version pinning strategy

**Decision**: Pin to major version tag (e.g., `@v4`, `@v5`, `@v2`) rather than SHA pinning
**Rationale**: Major version tags are the standard practice for public GHA actions. SHA pinning provides stronger supply-chain security but adds significant maintenance overhead (manual SHA updates per patch release). For a community skill project, major-version pinning is the right balance.
**Alternatives considered**: SHA pinning — better security posture but rejected for maintenance overhead. `@latest` — rejected; breaks on major version bumps.

---

## Decision 4: Loop prevention

**Decision**: release-please handles loop prevention natively — its own commits do not re-trigger the release job.
**Rationale**: release-please is aware of its own Release PR commits and does not create infinite release loops. No `[skip ci]` marker or author-checking condition is needed in the workflow.
**Alternatives considered**: `[skip ci]` in commit messages — this was the approach for a custom bump script but is no longer needed with release-please.
