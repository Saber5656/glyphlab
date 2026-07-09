# Title

CI: security scanning — pip-audit, bandit, gitleaks, dependency review

# Summary

Add a `security.yml` workflow running dependency-vulnerability, static-analysis, and
secret-scanning checks on every PR, plus a weekly scheduled run. This is the supply-chain and
secret-hygiene layer of DESIGN §17.3 (T10, T11).

# Context

The repository is public from day one and intends to ship a hosted service; security scanning
must exist before meaningful code does, so every subsequent issue lands under it.

# Scope

One workflow + tool configs. Fixing findings in dependencies chosen by later issues belongs to
those issues.

# Detailed Requirements

1. Workflow `security.yml`; triggers: `pull_request`, `schedule: cron "0 3 * * 1"`,
   `workflow_dispatch`; `permissions: contents: read`. Tools run via `uvx` (no dev-dep
   additions needed).
2. Jobs:
   - `pip-audit`:
     ```bash
     uv export --locked --no-emit-workspace --format requirements.txt -o /tmp/requirements.txt
     xargs -a security/pip-audit-ignores.txt -r -I{} echo --ignore-vuln {} | \
       xargs uvx pip-audit --strict -r /tmp/requirements.txt
     ```
     `security/pip-audit-ignores.txt`: one vulnerability ID per line, `#` comments required
     per entry justifying the ignore; empty initially.
   - `bandit`: `uvx --from 'bandit[toml]' bandit -c pyproject.toml -r packages/core/src
     packages/service/src --severity-level medium`. Root pyproject gets an empty
     `[tool.bandit]` table (zero skips initially; tests are not scanned because only `src`
     trees are passed).
   - `gitleaks`: two jobs from the official SHA-pinned action — `gitleaks-pr` (on PRs,
     default diff scan) and `gitleaks-full` (on schedule + workflow_dispatch, with
     `actions/checkout` `fetch-depth: 0` for full-history scanning per repo policy).
   - `npm-audit`: `npm audit --omit=dev --audit-level=high` in `webui/`, guarded by
     `if: hashFiles('webui/package-lock.json') != ''` so it activates when issue 39 lands
     (covers the DESIGN T10 `npm audit` requirement from day one).
   - `dependency-review`: `actions/dependency-review-action` (SHA-pinned) on PRs; deny
     `GPL-3.0` runtime deps (potrace is a subprocess/optional, ADR-004 documents the GPL-2
     boundary — allowlist `potracer` explicitly with a comment).
3. Dependabot config `.github/dependabot.yml`: weekly; ecosystems exactly `"uv"` (uv.lock
   support), `"github-actions"`, and `"npm"` with `directory: "/webui"`.
4. All actions SHA-pinned. No job requires secrets.
5. Document in workflow header: repo owner should also enable GitHub secret scanning + push
   protection in settings (human task — cannot be done from workflow files).

# Acceptance Criteria

- [ ] All PR-triggered jobs green on the introducing PR (they run there by definition).
- [ ] `gitleaks-full` green via `workflow_dispatch` with `fetch-depth: 0` visible in its
      log.
- [ ] Gitleaks canary: a fake AWS key committed to a throwaway branch is flagged by the
      PR job — verified once, branch deleted, never merged.
- [ ] `security/pip-audit-ignores.txt` and `[tool.bandit]` exist and are empty.
- [ ] Dependabot config contains exactly the three ecosystems above.

# Validation

```bash
# local reproduction of the two Python scanners:
uv export --locked --no-emit-workspace --format requirements.txt -o /tmp/requirements.txt
uvx pip-audit --strict -r /tmp/requirements.txt
uvx --from 'bandit[toml]' bandit -c pyproject.toml -r packages/core/src packages/service/src --severity-level medium
# live: open the introducing PR (runs pr jobs), then:
gh workflow run security.yml --ref "$(git branch --show-current)"
gh run watch "$(gh run list --workflow=security.yml --branch "$(git branch --show-current)" --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
```

# Dependencies

01, 02.

# Non-goals

CodeQL (optional post-v1 — heavyweight for this codebase), runtime security controls (28/29/31/
35/36/38), fixing vulnerabilities in not-yet-added dependencies.

# Design References

DESIGN §17.3 T10/T11 (supply chain, secrets); ADR-004 (GPL boundary note); repo policy:
history scan before publicizing (repo is already public — the gitleaks full-history job
covers it).
