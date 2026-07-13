# Title

Glyph endpoints: list, SVG serving, review

# Summary

Implement `GET /api/projects/{id}/glyphs` (paged listing with filters),
`GET /api/projects/{id}/glyphs/{cp}.svg` (safe SVG serving), and
`POST /api/projects/{id}/glyphs:review` (accept/reject batches) per DESIGN §15.

# Context

These endpoints power the web review grid (42). SVG serving to browsers demands the §17.3 T7
header discipline even though the SVGs are generator-produced.

# Scope

`packages/service/src/glyphlab_service/api/glyphs.py` + tests.

# Detailed Requirements

1. List route: query params `status` (repeatable, enum), `warning` (enum §9.5), `cursor`/
   `limit` (≤ 300, default 300 — one page covers ja-basic-v1 without pagination in
   practice; cursor = last codepoint, stable ordering by codepoint). Response exactly per
   §15: `{glyphs: [{codepoint: "U+3042", char: "あ", status, advance?, warnings[],
   svg_url?, updated_at}], next_cursor?}` — `svg_url` relative
   (`/api/projects/{id}/glyphs/U+3042.svg`) and present only when a stored SVG exists;
   `updated_at` ISO8601 (issue 42 uses it as a cache key).
2. SVG route: parse `{cp}` strictly as `U\+[0-9A-F]{4,6}` → int; must be in project charset
   (404 otherwise); fetch `glyphs/U+XXXX.svg` from store; **validate through issue 06's
   restricted parser before serving** (§17.3 T7 "restricted-subset-validated on read");
   validation failure → 500 `E_INTERNAL` + log (stored SVGs are generator-produced, so
   this should be impossible — treat as corruption, never serve the bytes). Headers:
   `Content-Type: image/svg+xml`, `X-Content-Type-Options: nosniff`,
   `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'`,
   `Cache-Control: private, max-age=60`, `Content-Disposition: inline;
   filename="U+XXXX.svg"`.
3. Review route: body `{accept: ["U+3042", ...], reject: [...]}`. Validation ladder:
   any string not matching `U\+[0-9A-F]{4,6}` → 422 `E_VALIDATION`; > 400 items total or
   non-disjoint accept/reject sets or duplicates within a list → 422; well-formed but
   outside the project charset OR status `missing` → per-item `errors[]` entry (200, not
   fatal). Transition rules identical to CLI issue 23 (accept: auto|rejected→accepted;
   reject: auto|accepted→rejected; no-ops counted as `unchanged`). Returns
   `{updated: N, unchanged: N, errors: [{codepoint, reason}]}`; single transaction.
4. All routes behind the 29 auth dependency; project id/token binding per T12 is inherited.
5. Tests: filter combinations; pagination edge (empty page, cursor beyond end); SVG headers
   exact; cp parsing rejects `U+41`, `U+GGGG`, path tricks (`U+0041%2F..`); review
   transition matrix incl. disjointness 422 and missing-item reporting; wrong token → 404
   everywhere.

# Acceptance Criteria

- [ ] Listing matches DB state for a corpus-ingested project (integration with 32's
      fixtures).
- [ ] SVG responses carry all four security headers; body parses via core restricted
      parser.
- [ ] Review is atomic: injected failure mid-batch rolls back all updates.
- [ ] Codepoint parser fuzz cases all 404/422 correctly.

# Validation

```bash
uv run pytest packages/service/tests/api/test_glyphs.py -q
```

# Dependencies

06, 29, 32 (glyph rows/SVGs produced by ingest jobs).

# Non-goals

Glyph editing/upload of user SVGs via API (v2 — CLI-only editing in v1), bulk export
endpoints.

# Design References

DESIGN §15 (routes), §17.3 T7/T12, §9.4–9.5, §5 (statuses).
