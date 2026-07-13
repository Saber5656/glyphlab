# Title

v1 acceptance run & release checklist

# Summary

Execute and automate the product-level acceptance of DESIGN §18.3: full CLI journey on two
corpus profiles, full hosted journey on the compose stack, retention behavior, the security
checklist walk (T1–T12), and performance budgets — producing a checked-in
`docs/ACCEPTANCE.md` report. Green here = v1 complete (ISSUE_PLAN §1).

# Context

Every wave has its own gates; this issue is the final integration pass that says the
*product* (not the parts) is done, and records evidence for the human release decision.

# Scope

`scripts/acceptance.sh` (or `packages/core/tests/acceptance/` marked suite) + one CI
workflow `acceptance.yml` (manual dispatch + weekly cron on main) + `docs/ACCEPTANCE.md`
template filled by the run.

# Detailed Requirements

1. Scripted acceptance (idempotent, single command):
   a. CLI journey ×2 profiles (`clean-scan`, `phone-tilt`) — reuses issue 25 machinery but
      via the installed wheel (`uv build` + venv install) not the workspace, catching
      packaging gaps.
   b. Compose stack up (issue 45's files with the `compose.e2e.yml` override) → hosted
      journey via the issue-44 Playwright suite.
   c. Retention (canonical mechanisms only — no DB hooks): do not set
      `GLYPHLAB_RETENTION_DAYS=0` in the hosted Playwright compose override from 44/45. Run
      retention as a separate one-shot acceptance step using a dedicated override/env with a
      very short but nonzero TTL (`GLYPHLAB_RETENTION_DAYS=0.001`, relying on issue 26's
      fractional-day setting) plus `GLYPHLAB_SWEEP_INTERVAL_S=5`; create a throwaway project
      via the API, wait long enough for that TTL + one sweep, assert the project 404s and its
      store prefix under the bind-mounted `e2e-data/` is gone. The normal hosted journey keeps
      a TTL that cannot expire projects during template download, upload, review, or build.
   d. Security walk: run the issue-38 suite in **container mode**
      (`ABUSE_BASE_URL=http://localhost:8080 uv run pytest packages/service/tests/abuse
      -q` — in-process-only tests self-skip per 38's marker); plus checklist assertions:
      image non-root + read-only fs (issue 45's docker-inspect commands), workflow
      hygiene (`scripts/check_workflow_hygiene.sh` over all workflows), `uvx pip-audit`
      clean, gitleaks job green on latest main run, Dependabot config present,
      `npm audit --omit=dev --audit-level=high` clean (T10/T11 evidence rows).
   e. Performance: record §21 numbers — stage wall-times from the runs, plus container
      memory via `docker stats --no-stream --format '{{.MemUsage}}'` sampled during the
      Playwright build step (must be < 800 MiB); fail if > budget ×1.5.
2. `docs/ACCEPTANCE.md`: generated table — item / DESIGN ref / result / evidence (log
   paths, artifact shas, timings, commit); committed by the human/agent after a green run
   (the file in-repo holds the latest accepted run; Validation asserts it exists and
   references the current HEAD's short SHA).
3. `acceptance.yml`: `workflow_dispatch` + weekly cron (`schedule: cron "0 4 * * 1"`)
   on main; artifacts: playwright traces, built fonts, acceptance report. SHA-pinned
   actions, `permissions: contents: read`.
4. Release checklist section in ACCEPTANCE.md (unchecked, for the human): version bump,
   tag, TestPyPI dry-run, PyPI approve (47), first deploy decision (46), announce.
5. Any failure found here files a bug referencing the owning issue's area — this issue is
   not the place to fix pipeline bugs (keep the diff to acceptance tooling).

# Acceptance Criteria

- [ ] One command produces a full green acceptance report on CI runners.
- [ ] Report contains evidence rows for: 2 CLI profiles, hosted journey, retention purge,
      every T1–T12 row (incl. the T10/T11 evidence items of req 1d), §21 budget numbers
      incl. container memory.
- [ ] Wheel-installed CLI (not workspace) used for the CLI journey.
- [ ] Validation block green, incl. workflow lint and committed report check.

# Validation

```bash
bash scripts/acceptance.sh                      # exits 0 and writes docs/ACCEPTANCE.md
test -s docs/ACCEPTANCE.md && grep -q "$(git rev-parse --short HEAD)" docs/ACCEPTANCE.md
bash scripts/check_workflow_hygiene.sh .github/workflows/acceptance.yml
grep -q 'cron: "0 4 \* \* 1"' .github/workflows/acceptance.yml
git status --porcelain docs/ACCEPTANCE.md       # empty after committing the run
```

# Dependencies

All of 01–48 (direct: 25, 38, 44, 45, 46, 47, 48).

# Non-goals

Real-handwriting quality validation (post-v1 human, ISSUE_PLAN §6.5), production deploy,
load testing.

# Design References

DESIGN §18.3, §21, §17.3, ISSUE_PLAN §1 (completion statement), §6 (validation strategy).
