# Contributing

Use Python 3.11/3.12, uv, Node 22+, and native potrace. The test corpus includes licensed
Klee One fixtures; no private handwriting is required.

```bash
uv sync --all-packages --all-extras
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/core/src
uv run pytest -q
uv run pytest packages/core/tests/e2e -m slow -q
cd webui
npm ci
npm run gen:api
npm run lint && npm run typecheck && npm test && npm run build
```

Use a task branch/worktree. Add a failing behavior test before changing production code,
run relevant checks, and review the diff for regressions and secrets before committing.
Submit a PR with English title/body and validation evidence; do not push directly to main.
The [issue plan](docs/ISSUE_PLAN.md) records dependencies and the v1 roadmap.

Generated API types must match the committed OpenAPI schema. Images, tokens and local
environment files must never be committed. See SECURITY.md for private reports.
