# TODOs

## Skill Marketplace / Registry

- [ ] Research agentskills.io spec and determine if `marketplace.json` or their manifest format
      is the right approach for publishing this skill to a registry.
- [ ] Decide whether to support multiple registries (agentskills.io, Claude skill marketplace,
      Copilot extensions marketplace) or target one first.
- [ ] Add the manifest file once format is decided and spec is validated.

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
