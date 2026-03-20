# TODOs

## Skill Marketplace / Registry

- [x] Add `.claude-plugin/marketplace.json` catalog (read by `/plugin marketplace add bdangit/myusage-skill`)
      and `.claude-plugin/plugin.json` manifest (read by `/plugin install myusage@myusage-skill`) —
      works with Claude Code and Copilot CLI `/plugin` commands.
- [ ] Research agentskills.io spec and determine if their manifest format requires changes to
      `plugin.json` for broader registry publishing.
- [ ] Decide whether to target additional registries (agentskills.io, Copilot extensions
      marketplace) beyond Claude Code / Copilot CLI.

## CI Pipeline

- [ ] **PR validation pipeline** — runs on every pull request:
  - Lint / syntax check (Python)
  - Run evals against fixtures
  - Validate SKILL.md is well-formed
  - Validate spec/plan artifacts are present for any feature branch

- [ ] **Mainline release pipeline** — runs on merge to `main`:
  - Automated version bump (semver)
  - Tag the release commit
  - Package the skill (`.skill` file or registry format)
  - Publish to registry (once marketplace format is decided)

## Cost / PRU Tracking (deferred from v1)

- [ ] Investigate Copilot CLI `assistant.usage.quotaSnapshots` with a real populated session
      to determine if PRU data is accessible there.
- [ ] Add a cost/PRU section to the report once data shape is confirmed.
      See `specs/001-usage-insights-report/spec.md` Future Considerations section.
