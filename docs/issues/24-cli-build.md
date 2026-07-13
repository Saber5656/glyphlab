# Title

CLI command: `build`

# Summary

Implement `glyphlab build`: select glyphs by status policy, re-read their SVGs through the
restricted parser, assemble TTF/WOFF2 (16), run the QA gate (17), generate the proof sheet
(18), and report artifacts — per DESIGN §13 and §10.1.

# Context

The command that produces the actual font. Glyph selection policy and the QA gate exit code
(4) live here; it is also where hand-edited SVGs re-enter the pipeline (trust boundary).

# Scope

`packages/core/src/glyphlab/cli/cmd_build.py` + the `collect_buildable_glyphs(store,
include_unreviewed)` helper in `fontbuild` + tests.

# Detailed Requirements

1. `glyphlab build [--include-unreviewed/--accepted-only] [--skip-bakery]
   [--completer none] [--out DIR]` (`--completer` accepts only `none` in v1 — DESIGN §9.6;
   any other value → exit 2):
   - Selection via `collect_buildable_glyphs(store, include_unreviewed: bool) ->
     dict[int, Path]` (helper in `fontbuild`; the CLI resolves the flag>config precedence
     and passes the boolean): `ACCEPTED` always; `AUTO` iff `include_unreviewed`;
     `REJECTED`/`MISSING` never. Zero selected drawn glyphs → `E_VALIDATION`, exit 3
     ("nothing to build; run ingest/accept").
   - Read each selected glyph SVG via issue-06 restricted parser (§17.4 limits enforced
     there); a failing SVG (hand-edit gone wrong) → collect ALL invalid ones and render one
     `E_GLYPH_SVG_INVALID` error whose detail lists every `file: reason`, exit 3 without
     building.
   - Version: `project.version` from config; output names `<family>-v<version>.ttf/.woff2`
     in `build/` (or `--out`); overwrite silently (build dir is machine-owned).
   - Assemble (16) → structural+bakery QA (17; `require_bakery=True` unless `--skip-bakery`,
     which prints a prominent warning) → proof (18) — the proof is generated **regardless
     of QA outcome** (parity with the service, issue 32) → print artifact table + QA
     summary. All four outputs (ttf, woff2, qa-report.json, proof.html) go to the same
     directory: `build/` or `--out DIR`.
   - QA failed → all artifacts still written; `E_QA_FAILED`, exit 4, failing check ids
     listed.
2. `--json` via issue 19's envelope: `data = {ttf, woff2, proof, qa: {passed, fails:
   [check_id]}, glyphs: {built: int, missing: ["U+XXXX"]}}`.
3. Warn (stderr) when building with `AUTO` glyphs: `N unreviewed glyphs included; run
   'glyphlab status' / 'accept' to review`.
4. Tests (corpus-backed golden project fixture): accepted-only vs include-unreviewed counts;
   invalid hand-edited SVG (fixture with a `transform` attr) → exit 3 naming the file; QA
   failure injection (monkeypatch a structural check) → exit 4, artifacts exist; happy path
   → font cmap coverage matches selection.

# Acceptance Criteria

- [ ] Selection policy matrix tested; exit codes 0/3/4 paths proven.
- [ ] Invalid-SVG batch reporting lists every bad file in one run.
- [ ] Built TTF passes issue-17 structural checks in the happy-path test.
- [ ] Proof sheet exists and references the same build (glyph counts match).

# Validation

```bash
uv run pytest packages/core/tests/cli/test_build.py -q
# smoke on the corpus-seeded fixture project (created by the test suite):
proj=$(uv run pytest packages/core/tests/cli/test_build.py::test_seed_project_path -q -s | tail -1)
uv run glyphlab --project "$proj" build --json | jq '.data.qa.passed'
```

# Dependencies

16, 17, 18, 19.

# Non-goals

Font installation helpers, watch/incremental builds, completer flags beyond `none` (§9.6).

# Design References

DESIGN §13, §10.1 (inputs), §11 (gate), §9.4 (SVG re-read), §9.6 (completer flag),
§17.4 (SVG limits), §22 (codes/exit 4).
