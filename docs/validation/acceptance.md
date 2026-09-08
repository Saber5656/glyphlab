# Product acceptance runner

Run `bash scripts/acceptance.sh` after installing Docker Compose, uv, Python 3.12,
Node, native potrace, and the workspace development dependencies. Install the
Playwright Chromium/WebKit browsers using `cd webui && npx playwright install
--with-deps chromium webkit`. Full acceptance requires committed implementation
inputs and an authenticated `gh` command able to read repository workflow runs.

The runner builds a fresh wheel and creates an isolated environment, then runs
all CLI commands through its installed console entry point. The fixture helper
is test-only; `python -I`, cleared `PYTHONPATH`/`PYTHONHOME`, and a site-packages
origin assertion prevent workspace imports from passing a broken-wheel check.

It starts the ordinary compose E2E stack with the normal 14-day TTL and samples
container memory throughout Playwright execution. A service restart before the
container abuse suite resets the test run's in-memory request counters without
weakening any production rate limit. Separate in-process and container JUnit
reports identify which attacks actually ran in each mode; a skipped test is
never described as a container pass.

Retention uses a separate compose project, port 18081, and a newly generated
bind mount. Its override sets `GLYPHLAB_RETENTION_DAYS=0.001` (86.4 seconds) and
`GLYPHLAB_SWEEP_INTERVAL_S=5`. Only public HTTP calls create and inspect the
throwaway project. The runner verifies both its authenticated 404 and removal
of its previously observed object-store prefix. It never edits database rows,
uses a zero TTL, or shortens the ordinary hosted journey's retention window.
New synthetic-test bind directories are writable by the non-root container UID
and readable by the host fixture helper; production storage permissions are not
changed.

`--stack-mode existing --compose-project NAME` uses a stack already started by
the integration operator (and does not tear it down). The operator must ensure
that stack uses the repository's E2E override and is dedicated to acceptance;
the runner restarts its service before container abuse. `--base-url` changes its
HTTP endpoint; `--retention-port` changes the isolated retention test endpoint.

`--only cli` performs the installed-wheel stage independently and saves **partial**
evidence under `work/acceptance/`. It does not write `docs/ACCEPTANCE.md`. A full
failure also leaves the last accepted report untouched and saves `evidence.json`,
logs, and `FAILURE.txt` for diagnosis. Pipeline or service defects discovered
here are assigned back to their owning implementation area.

## Report commit interpretation (issue 49 clarification)

A report cannot truthfully contain the hash of the commit that will later add
that report: adding its own hash changes the hash again. Therefore a successful
run records the complete immutable **tested commit**. Commit the resulting
`docs/ACCEPTANCE.md` as a report-only follow-up. Check that the tested commit is
an ancestor and the changes since it are report-only; never replace the tested
hash with an invented current HEAD value. Any implementation changes after the
run require fresh acceptance evidence.

The gitleaks row requires a successful `gitleaks-full` job from the latest
Security workflow run on `main`, and records that run's URL and SHA. A missing,
in-progress, skipped, or failed job keeps acceptance incomplete. This may mean
the first accepted report is a follow-up after the implementation merge and its
main-branch security run. No prefilled successful `docs/ACCEPTANCE.md` is shipped
by the tooling commit.
