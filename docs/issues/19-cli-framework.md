# Title

CLI framework: typer app, global flags, exit codes, error rendering

# Summary

Create the `glyphlab` CLI entry point per DESIGN §13: typer application skeleton, global
options (`--project`, `--json`, `--verbose`), the exit-code contract wired to the §22 error
registry, and consistent human/JSON output rendering. Commands themselves land in 20–24.

# Context

The DESIGN §13 commands (new/charset/template/ingest/status/accept/reject/build) share
flag handling, project resolution, error formatting, and exit-code mapping; centralizing
this first keeps each command issue mechanical. Per §13/§17.2 B5 the CLI performs no
network I/O — a socket-guard autouse fixture in the CLI test suite enforces it.

# Scope

`packages/core/src/glyphlab/cli/{main.py,context.py,render.py}` + `[project.scripts]
glyphlab = "glyphlab.cli.main:app"` in core pyproject + tests. Adds core deps: `typer`.

# Detailed Requirements

1. `main.py`: `app = typer.Typer(no_args_is_help=True, add_completion=True)`; version
   callback `glyphlab --version`; subcommand registration hooks for later issues (each
   command module exposes `register(app)`).
2. `context.py`: `CliContext{project_root: Path, json_mode: bool, verbose: bool}` built by a
   root callback from `--project PATH` (default `.`), `--json`, `--verbose`; helper
   `require_project(ctx) -> (ProjectConfig, ProjectStore)` that loads config or exits 3 with
   a clear message ("not a glyphlab project; run `glyphlab new`").
3. `render.py`:
   - Human mode: errors to stderr as `error[E_CODE]: message` where `message = str(exc)`
     and `detail` = issue 06's `GlyphlabError.detail` rendered as indented lines under
     `--verbose`; success output as plain tables (fixed-width, no color deps; `rich` NOT
     added — keep deps slim).
   - JSON mode (per §13): stdout carries exactly one machine envelope `{"ok": bool,
     "error": {code, message, detail}?, "data": ...}` in success AND failure; the
     human-readable error line still goes to stderr; nothing else on stdout.
4. Exit-code mapping per §13: wrap every command body in a decorator `cli_guard` that catches
   `GlyphlabError` → exit with `ERROR_REGISTRY[code].cli_exit` (3 validation/input, 4 QA),
   `typer.BadParameter` → 2, unexpected `Exception` → print traceback if `--verbose` else
   one-line + hint, exit 1.
5. A hidden `glyphlab _selftest` command exercising every exit path without a real
   project: `--ok` (prints nothing, exit 0), `--raise E_CODE` (raises the registered
   `GlyphlabError` → its `cli_exit`), `--raise-unexpected` (raises `RuntimeError` →
   exit 1), `--bad-param` (raises `typer.BadParameter` → exit 2).
6. Tests via `typer.testing.CliRunner`: version; help; exit codes 0/1/2/3/4 via the four
   `_selftest` flags (3 via `--raise E_VALIDATION`, 4 via `--raise E_QA_FAILED`); JSON
   mode purity (stdout parses as JSON in success and failure; exit code still non-zero on
   failure); socket-guard fixture active.

# Acceptance Criteria

- [ ] `uv run glyphlab --version` prints version; `--help` lists global options.
- [ ] Exit codes: 0/1/2/3/4 all covered by tests via `_selftest`.
- [ ] `--json` output parses as JSON in success and failure paths; stderr free of JSON.
- [ ] No command logic beyond `_selftest` in this issue.

# Validation

```bash
uv run glyphlab --help
uv run glyphlab _selftest --raise E_QA_FAILED; echo "exit=$?"   # expect exit=4
uv run pytest packages/core/tests/cli/test_framework.py -q
```

# Dependencies

05, 06.

# Non-goals

Individual commands (20–24), shell completion docs, localization (CLI is English; ja strings
are a web-UI concern §16.5).

# Design References

DESIGN §13 (commands table, exit codes), §22 (registry), §12 (project resolution).
