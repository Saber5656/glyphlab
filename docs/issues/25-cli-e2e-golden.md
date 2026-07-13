# Title

CLI end-to-end golden test: corpus → installable font

# Summary

A single scripted test that runs the entire local product — `new` → `template` → (synthetic
corpus as scans) → `ingest` → `accept` → `build` — and asserts font-level ground truth. This
is the Wave-4 exit gate ("local product complete") and the calibration point for the
fontbakery allowlist (KU-4).

# Context

Individual issues test stages; this issue proves the composition, catches contract drift
between CLI commands, and pins performance budgets (§21) with real numbers.

# Scope

`packages/core/tests/e2e/test_cli_golden.py` (+ allowlist calibration commit to
`packages/core/src/glyphlab/qa/allowlist.toml` with justifications if needed). No
production code changes except those justified by findings (each finding fixed in its
owning module with a linked commit). Also extends issue 02's CI workflow with a dedicated
`e2e` job running `uv run pytest packages/core/tests/e2e -m slow -q` (the plain matrix job
excludes `-m slow` by default via pytest config addopts `-m "not slow"` — adjust in this
issue and document).

# Detailed Requirements

1. Test flow (tmpdir; every command invoked with `--project <tmp>/e2e`; at least one step
   via real `uv run glyphlab ...` subprocess to validate the console script, the rest via
   `CliRunner` for speed):
   a. `new e2e --charset ja-basic-v1 --family-name E2EHand --dir <tmp>/e2e`.
   b. `template`; read sidecar; generate `clean-scan` corpus for THIS template via issue
      09's `generate_corpus(template_pdf, sidecar, ...)` — per-test, so template_id
      matches.
   c. Copy corpus pages into `scans/`; `ingest`; assert coverage == manifest ink counts.
   d. `accept --all-auto`; `build`.
   e. Assertions on the TTF (fontTools): cmap == expected coverage + synthesized; kana AND
      punct_ja advances 1000; U+0020 500 / U+3000 1000; no empty drawn outlines; points
      within §11.2 bounds; OS/2/head per §10.3; fontbakery gate passed (allowlist
      justified if calibrated). proof.html: exists, contains coverage numbers, passes the
      issue-18 self-containment assertions (CSP meta present, no non-data URIs).
   f. Create a second fresh project and repeat copy→ingest→coverage assertions→accept→build
      with the `phone-tilt` corpus before any glyphs are accepted in that project. This must
      exercise the tilted vectorization/build path rather than only the accepted-glyph skip.
   g. Separately, re-ingest `phone-tilt` into the first already-accepted project to cover the
      §8.3 skip path; accepted glyphs are skipped and the build still stays green.
2. Performance recording: wall-time measured test-side (`time.perf_counter` around each
   CLI invocation, divided by page count for per-page ingest) and asserted against §21
   budgets ×1.5 slack on CI (page ingest ≤ 22.5 s, build ≤ 15 s); marked `slow` (runs in
   the CI `e2e` job; locally via `-m slow`).
3. Determinism: `SOURCE_DATE_EPOCH` fixed; two full runs produce byte-identical TTFs.
4. Any deviation discovered (allowlist needs, tuning) must be committed with an explanatory
   entry, not hidden in the test.

# Acceptance Criteria

- [ ] Full journey green on ubuntu + macos CI.
- [ ] Byte-reproducibility across two runs proven.
- [ ] Budgets recorded in test output; failures block.
- [ ] `qa/allowlist.toml` entries (if any) each carry a `reason`.

# Validation

```bash
uv run pytest packages/core/tests/e2e -m slow -q
```

# Dependencies

09, 20, 21, 22, 23, 24.

# Non-goals

Service/web journeys (37/38/44/49), real handwriting validation (post-v1 human step).

# Design References

DESIGN §18.2–§18.3, §21, §2.4 KU-4, ISSUE_PLAN §4 (W4 exit criterion).
