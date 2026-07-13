# Title

CLI commands: `status`, `accept`, `reject`

# Summary

Implement coverage reporting and the review workflow per DESIGN §13: `status` (counts,
warnings, missing list) and `accept`/`reject` (status transitions on codepoint sets).

# Context

Review is what separates `AUTO` extraction from a user-approved glyph set (§8.3 protects
`ACCEPTED` glyphs from silent overwrite; this issue is where users create that protection).

# Scope

`packages/core/src/glyphlab/cli/{cmd_status.py,cmd_review.py}` + codepoint-set argument
parser + tests.

# Detailed Requirements

1. Codepoint-set parser (shared helper): accepts `U+3042`, literal chars (`あ`, multi-char
   strings expand per char), inclusive ranges `U+3041-U+3096`, and selectors `--all-auto`
   (every glyph with status `AUTO`) / `--all-warned CODE` (every glyph whose warnings
   contain CODE **regardless of current status**; CODE validated against the §9.5 enum,
   invalid → exit 3; empty match → no-op with "0 matched" message, exit 0); validates
   membership in the project charset (unknown → exit 3 listing offenders).
2. `glyphlab status [--missing] [--warned]`:
   - Header: project name, charset id@version, template state (generated? template_id
     prefix).
   - Table: `status | count` rows for missing/auto/accepted/rejected plus a `total` row
     (= drawn glyph count, per DESIGN §13) + synthesized note; warnings breakdown
     `warning | count`.
   - `--missing`: list missing codepoints as compact ranges + literals;
     `--warned`: list `U+XXXX char [codes]`.
   - JSON via issue 19's envelope: `data = {"counts": {"total": int, "missing": int,
     "auto": int, "accepted": int, "rejected": int}, "warnings": {CODE: int},
     "glyphs": {"U+3042": {"status": str, "warnings": [str]}}}`.
3. `glyphlab accept SET...` / `glyphlab reject SET...`:
   - Transition rules: accept: `AUTO|REJECTED → ACCEPTED` (missing → error listing them;
     already-accepted → no-op counted); reject: `AUTO|ACCEPTED → REJECTED`.
   - Prints `accepted 12, already 3, missing 1 (U+3099)`; exit 3 if any missing requested,
     0 otherwise; store writes atomic (05).
4. Tests: parser property tests (round-trip formatting), transition matrix, status output
   snapshot on a seeded project fixture.

# Acceptance Criteria

- [ ] All parser forms + invalid inputs covered by tests.
- [ ] Transition matrix enforced exactly (no `missing → accepted`).
- [ ] `status --json | jq` shows per-glyph statuses matching store.
- [ ] Range listing in `--missing` is compact (e.g. `U+3041-U+3044` not 4 lines).

# Validation

```bash
uv run pytest packages/core/tests/cli/test_status_review.py -q
# manual smoke on a seeded fixture project produced by the test suite:
proj=$(uv run pytest packages/core/tests/cli/test_status_review.py::test_seed_project_path -q -s | tail -1)
uv run glyphlab --project "$proj" accept "あいうえお"
uv run glyphlab --project "$proj" status --json | jq '.data.counts'
```

# Dependencies

05, 06, 19.

# Non-goals

Visual review (web UI 42; proof sheet 18 covers local eyeballing), editing glyph geometry.

# Design References

DESIGN §13, §5 (GlyphStatus), §8.3 (accepted protection rationale).
