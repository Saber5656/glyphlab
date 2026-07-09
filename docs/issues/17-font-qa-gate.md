# Title

Font QA gate: fontbakery universal profile + structural self-checks

# Summary

Implement DESIGN §11.1–§11.2: fast structural assertions that always run, plus a fontbakery
`check-universal` subprocess wrapper with a justified allowlist; produce `qa-report.json` and
gate builds with `E_QA_FAILED`.

# Context

Users install these fonts into their OS; shipping structurally broken fonts is the product
failing at its one job. The gate must be automatic so implementation agents cannot skip it.

# Scope

`packages/core/src/glyphlab/qa/{model.py,structural.py,bakery.py,allowlist.toml,
report.schema.json}` + tests. Adds dev/optional dependency `fontbakery` (extra
`glyphlab[qa]`; also a dev dep so CI always has it).

Types (`qa/model.py`): `QAFinding{check_id: str, severity: FAIL|WARN|SKIPPED|ALLOWED,
message: str, detail: dict | None}`; `QAReport{passed: bool, findings: list[QAFinding]}`
(§11.1 canonical shape); `ExpectedBuild{codepoints: set[int], advances: dict[int, int]}` —
constructed by callers (24/32) from the charset + their glyph selection.

# Detailed Requirements

1. `structural.py`: `run_structural_checks(ttf_path, charset, expected: ExpectedBuild) ->
   list[QAFinding]` implementing §11.2 exactly:
   - cmap == expected codepoint set (accepted/included ∩ charset + synthesized), no extras.
   - advances: every kana/punct_ja == 1000; U+0020 == 500; U+3000 == 1000; all ≥ 120.
   - no empty outlines for drawn glyphs; all points within x ∈ [−200, 2000], y ∈ [−250,
     1000].
   - head/hhea/OS/2 values exactly §10.3; fsType 0; UPM 1000.
   Each violation → `QAFinding{check_id, severity: FAIL, message, detail}`.
2. `bakery.py`: `run_fontbakery(ttf_path) -> list[QAFinding]`:
   - Subprocess: `fontbakery check-universal --json <tmp> --no-progress --loglevel WARN
     <ttf>` with 120 s timeout (per §11.1 — allowlist post-processing replaces fontbakery
     configuration files); parse the JSON log; map ERROR/FAIL results to FAIL findings,
     WARN to WARN (check id = fontbakery check id).
   - Allowlist `allowlist.toml`: `[[allow]] check = "com.google.fonts/check/..."` with
     mandatory `reason = "..."` — findings matching an allow entry downgrade to `severity:
     ALLOWED`. Empty initially; populated during first golden build (KU-4) via a follow-up
     commit with justifications.
   - fontbakery not installed → behavior depends on `require_bakery: bool`:
     `True` → `E_VALIDATION`-style failure finding telling the caller to install
     `glyphlab[qa]`; `False` → finding `severity: SKIPPED` with the same hint. Callers:
     CLI `build` passes `require_bakery=True` unless `--skip-bakery` (issue 24); service
     builds always pass `True` (issue 32). This module has no default of its own — the
     parameter is required.
3. `run_qa(ttf, charset, expected, *, require_bakery) -> QAReport`;
   `passed = no FAIL findings`; serialize to `qa-report.json` with top-level
   `"schema": "glyphlab.qa-report/1"`, validated by the checked-in
   `packages/core/src/glyphlab/qa/report.schema.json`.
4. Failure raises nothing by itself; callers (24/32) raise `E_QA_FAILED` when
   `passed == False` — report always written.
5. Tests: build the golden font at test time via issue 16's `golden_font` fixture (no
   committed binary); it passes; corrupt variants (advance 999 on kana; missing U+3042
   from cmap while expected; winAscent 500 — produced by mutating with fontTools and
   re-saving) each produce the precise finding; allowlisted finding downgrades to ALLOWED;
   fontbakery-missing path: SKIPPED when `require_bakery=False`, FAIL finding with install
   hint when `True`.

# Acceptance Criteria

- [ ] All structural checks implemented with one test each proving detection (incl. the
      §11.2 advance ≥ 120 floor and x ∈ [−200, 2000] bounds).
- [ ] fontbakery wrapper parses real output of `fontbakery==1.1.x` on the golden font in CI.
- [ ] `qa-report.json` validates against `qa/report.schema.json`; findings sorted by
      check id.
- [ ] Allowlist entries without `reason` fail a config unit test.

# Validation

```bash
uv run pytest packages/core/tests/qa -q
```

# Dependencies

16.

# Non-goals

Proof sheet (18), calibrating the allowlist contents (KU-4, done during 25), rendering
screenshots.

# Design References

DESIGN §11.1, §11.2, §22 (`E_QA_FAILED`), §2.4 KU-4; research/01 (fontbakery CLI).
