# Title

PyPI packaging & release workflow (Trusted Publishing)

# Summary

Make `packages/core` publishable as `glyphlab` on PyPI: complete metadata, wheel content
correctness, a tag-triggered GitHub Actions release workflow using Trusted Publishing (OIDC,
no long-lived tokens), and a TestPyPI dry-run path — per DESIGN §20.

# Context

The CLI persona installs via `pip install glyphlab`. The PyPI name is free as of 2026-07-08
(research/01, KU-6) and should be claimed at first release. Release remains a human-gated
action (merge ≠ release, repo policy).

# Scope

Core pyproject metadata, `release.yml` workflow, `CHANGELOG.md` seed, packaging tests. No
actual first publish (human decision).

# Detailed Requirements

1. Metadata (`packages/core/pyproject.toml`): description, readme, license `MIT`,
   authors, keywords (font, handwriting, japanese, kana), classifiers (Python 3.11/3.12,
   Topic :: Text Processing :: Fonts, License :: OSI Approved :: MIT License), urls
   (Homepage=repo, Issues, Changelog), extras finalized: `trace` (potracer), `qa`
   (fontbakery). Dependencies audited against research/01's exact names and lower bounds:
   `fonttools>=4.63`, `brotli>=1.2`, `reportlab>=5.0`, `opencv-python-headless>=4.8`,
   `numpy`, `pillow>=12`, `pillow-heif>=1.4`, `skia-pathops>=0.9`, `typer>=0.26`,
   `pydantic>=2.13`; no upper pins except known breakage.
2. Wheel content test (pytest): build with `uv build --package glyphlab`; assert the
   wheel contains only `glyphlab/**` **plus the standard `glyphlab-*.dist-info/**`
   metadata** (METADATA, entry_points.txt with the `glyphlab` script, licenses/LICENSE) —
   and nothing else (no tests, no service, no corpus fonts); `pip install dist/*.whl &&
   glyphlab --version` works in a clean venv (tox-free subprocess test).
3. `release.yml`: triggers `push: tags: ["v*"]` and `workflow_dispatch` with boolean input
   `dry_run` (default `true`) plus optional `version` input so branch dry-runs can execute
   before a tag exists; manual `workflow_dispatch` is dry-run only, and publish jobs are
   additionally guarded with `github.event_name == 'push' &&
   startsWith(github.ref, 'refs/tags/v')`;
   jobs: `check-tag` (runs `scripts/check_tag_version.sh` — asserts `${TAG#v}` is a valid
   PEP 440 version via `packaging.version.Version` AND equals `glyphlab.__version__`; for
   `workflow_dispatch` dry-runs, uses the `version` input or current `glyphlab.__version__`
   instead of `${TAG#v}`;
   prereleases like `v0.0.1a0` are therefore valid) → `build` (`uv build --locked`,
   upload dist artifact) → `test-install` (matrix 3.11/3.12, install wheel, run
   `glyphlab charset list`) → `publish-testpypi` (skipped unless the event is a `v*` tag push
   and `dry_run` is not true; environment `testpypi`,
   `pypa/gh-action-pypi-publish` SHA-pinned, `repository-url` TestPyPI, Trusted
   Publishing via `permissions: id-token: write` on that job only) → `publish-pypi`
   (skipped unless the event is a `v*` tag push and `dry_run` is not true) gated on
   **environment `pypi` with required reviewers** (human approval click = the
   release gate; builds happen only in CI per §17.3 T10). The whole workflow passes
   `scripts/check_workflow_hygiene.sh` (issue 02): every action SHA-pinned, minimal
   per-job permissions, no `secrets.` references (OIDC only).
4. `CHANGELOG.md`: Keep-a-Changelog format, `Unreleased` section seeded; release workflow
   reminds (comment) that the tag annotation should copy the section.
5. Docs: `docs/RELEASING.md` — exact human steps: bump version PR → merge → `git tag
   -s vX.Y.Z && git push --tags` → approve environments; **[HUMAN]** one-time setup:
   configure PyPI/TestPyPI Trusted Publisher for the repo + create GitHub environments
   (cannot be done from workflow files).
6. No secrets in the workflow (OIDC only); `permissions` minimal per job.

# Acceptance Criteria

- [ ] `uv build` artifacts pass the wheel-content test in CI.
- [ ] `release.yml` dry-run: `workflow_dispatch` variant with `dry_run=true` input skips
      both publish jobs and runs check-tag/build/test-install green (this is the
      documented dry-run method; no fork needed).
- [ ] Tag consistency: Validation's negative test fails on a mismatched tag.
- [ ] RELEASING.md + CHANGELOG.md checks in Validation pass.

# Validation

```bash
uv build --package glyphlab && uv run pytest packages/core/tests/test_packaging.py -q
bash scripts/check_workflow_hygiene.sh .github/workflows/release.yml
TAG=v9.9.9 bash scripts/check_tag_version.sh && echo "FAIL: should mismatch" || echo "mismatch detected OK"
TAG="v$(uv run python -c 'import glyphlab;print(glyphlab.__version__)')" bash scripts/check_tag_version.sh
grep -q "## \[Unreleased\]" CHANGELOG.md
grep -c "\[HUMAN\]" docs/RELEASING.md   # expect ≥ 2
gh workflow run release.yml -f dry_run=true --ref "$(git branch --show-current)" && gh run watch --exit-status "$(gh run list --workflow=release.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
```

# Dependencies

02, 03, 25 (release quality bar: golden E2E green).

# Non-goals

Publishing the service package (never), Docker registry publishing (post-v1), signing
beyond PyPI attestations default, first actual release (human decision post-v1).

# Design References

DESIGN §20 (PyPI), §2.4 KU-6, §17.3 T10 (locked builds, pinned actions, CI-only release
builds; OIDC instead of long-lived tokens), repo policy (merge ≠ release).
