# Quickstart: GHA CI/CD Pipeline

## For contributors — validate locally before pushing

```bash
# From repo root
.github/scripts/validate.sh
```

That's it. Exit 0 = all checks pass. Non-zero = something needs fixing before opening a PR.

**Requires**: Python 3.10+ on your `$PATH`.

---

## For maintainers — how releases work

Releases are fully automatic on merge to `main`. No manual steps needed.

1. Merge a PR to `main`
2. The `validate` job runs — if it fails, the release job is skipped
3. If validate passes, the `release` job:
   - Inspects commit messages since the last tag to determine bump level
   - Updates `plugin.json` with the new version
   - Commits with `[skip ci]` (no release loop)
   - Creates git tag `vX.Y.Z`
   - Publishes a GitHub Release with auto-generated notes

### Bump levels

| Commit pattern | Bump |
|---------------|------|
| `feat!:`, `fix!:`, or `BREAKING CHANGE:` in body | Major (`X+1.0.0`) |
| `feat:` | Minor (`X.Y+1.0`) |
| `fix:` or anything else | Patch (`X.Y.Z+1`) |

---

## For maintainers — checking the current version

```bash
python3 -c "import json; print(json.load(open('.claude-plugin/plugin.json'))['version'])"
```

---

## Branch protection setup (one-time, after workflow is merged)

In GitHub → repo Settings → Branches → Add rule for `main`:
- Enable **Require status checks to pass before merging**
- Add `validate` (the job name from `ci.yml`) as a required check
