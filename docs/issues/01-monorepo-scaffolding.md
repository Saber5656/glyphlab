# Title

Monorepo scaffolding: uv workspace, core package, tooling baseline

# Summary

Create the repository skeleton defined in DESIGN §4: a uv workspace with `packages/core`
(distribution name `glyphlab`) and `packages/service` (`glyphlab-service`), shared lint/type/
test tooling, license, and hygiene files. No product logic.

# Context

Every other issue assumes this layout, these commands, and these quality gates. The repo
currently contains only `README.md` and the `docs/` tree (design, ADRs, issue drafts) — no
code. DESIGN §4 also shows `webui/`, `deploy/`, and `tests/fixtures/`; those are created by
issues 39, 45, and 09 respectively and are **not** part of this issue.

# Scope

- Workspace + package skeletons with empty-but-importable modules and one placeholder test each.
- Tooling config: ruff, mypy, pytest, pre-commit.
- `LICENSE` (MIT, copyright holder "glyphlab contributors"), `.gitignore`, `.editorconfig`.
- `README.md`: keep the existing Japanese one-liner; add a short English subtitle and a
  "status: under construction" note (full README is issue 48).

# Detailed Requirements

1. Root `pyproject.toml`: `[tool.uv.workspace] members = ["packages/core", "packages/service"]`;
   shared `[tool.ruff]` (line-length 100, `select = ["E","F","I","UP","B","S"]`, and
   `[tool.ruff.lint.per-file-ignores]` with `"**/tests/**" = ["S101"]` so pytest asserts
   pass the flake8-bandit rules), `[tool.mypy]` (`strict = true` for `packages/core/src`),
   `[tool.pytest.ini_options]` (`testpaths = ["packages"]`).
   Dev tooling lives in the root `[dependency-groups] dev = ["pytest>=8", "mypy>=1.14",
   "ruff>=0.8", "pre-commit>=4"]` — installed by default with `uv sync`, so every
   Validation command below runs via `uv run`.
2. `packages/core/pyproject.toml`: name `glyphlab`, `requires-python = ">=3.11"`, version
   `0.1.0.dev0`, `dependencies = []` for now (each later issue adds only what it needs);
   optional extras placeholders: `trace = []` (filled by issue 13). Build backend: hatchling.
   `[project.scripts] glyphlab = "glyphlab.cli.main:app"` may be added in issue 19 — do NOT add
   it here (module does not exist yet).
3. `packages/core/src/glyphlab/__init__.py` with `__version__`; subpackage dirs from DESIGN §4
   (`charset/ template/ ingest/ vectorize/ fit/ fontbuild/ qa/ report/ project/ cli/`), each
   with empty `__init__.py`.
4. `packages/service/pyproject.toml`: name `glyphlab-service`, version `0.1.0.dev0`,
   `requires-python = ">=3.11"`, build backend hatchling, not intended for PyPI
   (`classifiers = ["Private :: Do Not Upload"]`), `dependencies = ["glyphlab"]` resolved
   via workspace source (`[tool.uv.sources] glyphlab = { workspace = true }`).
5. `packages/service/src/glyphlab_service/__init__.py` only (app factory is issue 26).
6. `.pre-commit-config.yaml`: ruff (lint+format), `uv lock --check`, end-of-file/trailing-ws
   hooks. Pin hook revs.
7. `uv.lock` committed. `uv sync && uv run pytest` must pass from a clean clone.
8. Placeholder tests: `packages/core/tests/test_import.py` asserting `import glyphlab` and
   version string; same pattern for service.
9. `.gitignore`: Python + Node + `.env` + `work/` + `dist/` + `.venv/`.

# Acceptance Criteria

- [ ] All Validation commands exit 0 locally (macOS or Linux; the cross-platform matrix is
      proven by issue 02's CI, not here).
- [ ] `LICENSE` first line is "MIT License" and the file matches the OSI MIT text
      (Validation grep).
- [ ] README still contains the original Japanese one-liner (Validation grep).
- [ ] `packages/` contains no logic beyond `__version__` and imports (reviewer check:
      diff is only scaffolding).

# Validation

```bash
git clean -ndx | head             # inspect; then run from a fresh sync:
uv sync
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/core/src
uv run pre-commit run --all-files
head -1 LICENSE                   # expect: MIT License
grep -c "手書き文字から自分のフォントを作る" README.md   # expect: 1
```

All commands exit 0.

# Dependencies

None.

# Non-goals

CI workflows (02/03), any pipeline/service code, webui scaffold (39), packaging metadata polish
(47).

# Design References

DESIGN §4 (repository layout), §2.1 G4/G5 (two packages rationale), ADR-001.
