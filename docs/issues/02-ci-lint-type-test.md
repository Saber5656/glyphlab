# Title

CI: lint, type-check, and test workflow (GitHub Actions)

# Summary

Add `.github/workflows/ci.yml` running ruff, mypy, and pytest for the Python workspace on every
PR and push to `main`, on Ubuntu and macOS, Python 3.11 and 3.12.

# Context

DESIGN §18.1 requires unit/golden/property suites to gate every PR. Later issues (webui,
contract, E2E) extend CI; this issue establishes the base workflow they hook into.

# Scope

One workflow file + `scripts/check_workflow_hygiene.sh` + README badge line.
Branch-protection/ruleset configuration is a human task (repo settings) — document the
recommended required check names in the workflow file header comment (req 7).

# Detailed Requirements

1. Workflow `ci.yml`, triggers: `pull_request`, `push: branches [main]`,
   `workflow_dispatch`. `permissions: contents: read` (top level).
2. Job `python` matrix: `os: [ubuntu-latest, macos-latest]`, `python: ["3.11", "3.12"]`.
   Steps: checkout → `actions/setup-python` (SHA-pinned) with
   `python-version: ${{ matrix.python }}` → `astral-sh/setup-uv` (pin by commit SHA,
   enable cache) → `UV_PYTHON=${{ matrix.python }} uv sync --locked` → `uv run ruff
   check .` → `uv run ruff format --check .` → `uv run mypy packages/core/src` → `uv run
   pytest -q --maxfail=5`. The check log must include `python --version` and `uv python
   list --only-installed` so the matrix label is tied to the interpreter actually used.
3. `uv sync --locked` must fail the build on lockfile drift.
4. System deps step (exact form):
   ```yaml
   - name: Install potrace (Linux)
     if: runner.os == 'Linux'
     run: sudo apt-get update && sudo apt-get install -y --no-install-recommends potrace
   - name: Install potrace (macOS)
     if: runner.os == 'macOS'
     run: brew install potrace
   ```
5. Concurrency group cancels superseded runs of the same ref:
   `concurrency: {group: ci-${{ github.ref }}, cancel-in-progress: true}`.
6. Every third-party action pinned to a full commit SHA (security posture, DESIGN §17.3 T10).
7. Job/check names are part of the contract (branch protection will reference them):
   matrix cells surface as `python (ubuntu-latest, 3.11)`, `python (ubuntu-latest, 3.12)`,
   `python (macos-latest, 3.11)`, `python (macos-latest, 3.12)`. List these four names in
   the workflow header comment as the recommended required checks.
8. README: add a CI badge as the first line under the title:
   `[![CI](https://github.com/Saber5656/glyphlab/actions/workflows/ci.yml/badge.svg)](https://github.com/Saber5656/glyphlab/actions/workflows/ci.yml)`.
9. Total runtime target < 10 min; use uv cache (`enable-cache: true` on setup-uv).

# Acceptance Criteria

- [ ] Workflow passes on the PR that introduces it (all 4 matrix cells, names as in req 7).
- [ ] Lint-failure canary (see Validation step 3) fails CI on its throwaway branch; branch
      deleted afterwards; never merged.
- [ ] `bash scripts/check_workflow_hygiene.sh` (added by this issue) exits 0: every `uses:`
      is SHA-pinned, top-level `permissions:` is `contents: read`, no `secrets.` references
      in `ci.yml`.
- [ ] README badge renders (URL matches req 8).

# Validation

```bash
# 1. Static hygiene (script added by this issue; greps ci.yml):
bash scripts/check_workflow_hygiene.sh .github/workflows/ci.yml
# expects: every 'uses:' matches '@[0-9a-f]{40}', 'permissions:\n  contents: read' present,
# zero occurrences of 'secrets.'

# 2. Live run on the feature branch:
git push -u origin HEAD
gh workflow run ci.yml --ref "$(git branch --show-current)"
gh run watch "$(gh run list --workflow=ci.yml --branch "$(git branch --show-current)" --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status

# 3. Lint canary on a throwaway branch (never merged):
git checkout -b ci-canary-lint && echo "import os" >> packages/core/src/glyphlab/__init__.py
git commit -am "canary: unused import" && git push -u origin ci-canary-lint
gh run watch "$(gh run list --workflow=ci.yml --branch ci-canary-lint --limit 1 --json databaseId --jq '.[0].databaseId')" && echo "expect FAILURE above"
git checkout - && git push origin --delete ci-canary-lint && git branch -D ci-canary-lint
```

# Dependencies

01.

# Non-goals

Security scanners (03), webui CI (39), release workflows (47), enabling GitHub branch
protection itself (human task).

# Design References

DESIGN §18.1 (layer table), §17.3 T10 (pinned actions).
