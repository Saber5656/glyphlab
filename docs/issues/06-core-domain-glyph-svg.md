# Title

Core domain model, error registry, and glyph SVG format (writer + restricted parser)

# Summary

Implement `Glyph`/`GlyphOutline`/contour geometry types, the `GlyphStatus`/`GlyphWarning`
enums, the canonical error-code registry (DESIGN §22), and the glyph SVG intermediate format:
serializer and the security-hardened restricted parser (DESIGN §9.4).

# Context

Every pipeline stage exchanges these types; the SVG intermediate is both a user-editable
artifact (CLI persona P2) and an input re-read at build time — making its parser a trust
boundary (§17.4): a hand-edited or maliciously crafted SVG must not be able to smuggle
anything beyond outline geometry.

# Scope

`packages/core/src/glyphlab/{model.py,errors.py}` and
`packages/core/src/glyphlab/project/glyph_svg.py` + tests.

# Detailed Requirements

1. `model.py`: types from DESIGN §5 — `Point(x: float, y: float)`, `CubicSegment(p1, c1, c2,
   p2)`, `Contour(segments: tuple[CubicSegment,...])` with `is_closed` invariant (first point
   == last segment end), `GlyphOutline(contours)`, `Glyph`, `GlyphStatus`, `GlyphWarning`
   (§9.5 codes), `GlyphSourceRef(upload: str, cell: int)`.
   Geometry helpers: `GlyphOutline.bbox() -> (xmin, ymin, xmax, ymax)`, `transform(scale,
   dx, dy)` returning new outline (pure).
2. `errors.py`: `GlyphlabError(Exception)` base with `code: str` from the §22 registry
   and an optional structured `detail: dict[str, object] | None` (machine-readable payload
   surfaced in the HTTP envelope `error.detail` and CLI `--verbose` output);
   `ERROR_REGISTRY: dict[str, ErrorSpec]` where `ErrorSpec = {code, http_status: int,
   cli_exit: int, description}` — one entry per row of the DESIGN §22 table, with exactly
   the HTTP and CLI-exit values from that table (`E_QUOTA_EXCEEDED` stores 409; the 507
   global-storage variant is applied by the endpoint, noted in the spec's description).
   Also provide `to_glyphlab_error(exc) -> GlyphlabError` mapping issue 04's
   `UnknownCharsetError` → `E_VALIDATION` (06 depends on 04, so the import is legal).
   Later modules that depend on this issue raise `GlyphlabError` subclasses directly.
   Unit test asserts registry completeness (every §22 code present; every `GlyphlabError`
   subclass's code registered) and uniqueness.
3. `glyph_svg.py` — writer:
   `write_glyph_svg(path, outline: GlyphOutline, codepoint: int, advance: int)` emitting
   exactly the §9.4 document: `viewBox="0 -880 {advance} 1000"`, y-flip applied (font y-up →
   SVG y-down: `svg_y = -font_y`), one `<path>` with `M/C/L/Z` only, `data-glyphlab="glyph/1"`,
   `data-codepoint="U+XXXX"`, `data-advance`. Deterministic output (fixed decimal precision:
   2 dp, no scientific notation).
4. `glyph_svg.py` — restricted parser `read_glyph_svg(path) -> tuple[GlyphOutline, int]`
   (the `int` is the advance, taken from `data-advance`):
   - Parse with `xml.etree.ElementTree` using a defusedxml-style hardening: reject documents
     containing DOCTYPE, entity declarations, or processing instructions (raise
     `GlyphSvgInvalidError` = `E_GLYPH_SVG_INVALID`).
   - Accept ONLY: root `svg` (any xmlns) with attributes `xmlns`, `viewBox`,
     `data-glyphlab`, `data-codepoint`, `data-advance`; children: exactly one `path` element
     with `d` and optional `fill`. Any other element/attribute → reject.
   - Attribute validation: `data-glyphlab` must equal `glyph/1`; `data-codepoint` must match
     `U\+[0-9A-F]{4,6}`; `data-advance` integer in [120, 2000]; `viewBox` must equal
     `0 -880 {advance} 1000` with the same advance; `fill`, when present, must be `black`,
     `#000`, or `#000000` — anything else (e.g. `url(...)`) → reject.
   - `d` grammar: `M`, `L`, `C`, `Z` (absolute only), decimal numbers; hand-written lowercase/
     relative commands → reject with a message naming the offending token. Max size 256 KiB,
     max 64 contours, max 4000 segments (§17.4).
   - Coordinates clamped-checked: |x|,|y| ≤ 4000 font units else reject.
   - Round-trip: `read(write(outline))` reproduces geometry within 0.01 units.
5. Property tests (hypothesis, added to the dev dependency group; register a `ci` profile
   with `max_examples=1000` used by the round-trip test): random outlines survive
   write→read round-trip; malformed-SVG fixtures under
   `packages/core/tests/glyph_svg/malformed/` — exactly these ten files, each rejected with
   `E_GLYPH_SVG_INVALID`: `01-doctype.svg`, `02-entity.svg`, `03-script-element.svg`,
   `04-image-href.svg`, `05-transform-attr.svg`, `06-two-paths.svg`,
   `07-relative-commands.svg`, `08-fill-url.svg`, `09-bad-viewbox.svg`,
   `10-oversize-256k.svg`.

# Acceptance Criteria

- [ ] Round-trip property test green with `max_examples=1000` under the `ci` profile.
- [ ] All 10 named malformed-SVG fixtures rejected; each error message names the reason.
- [ ] Error registry test: every §22 code present with the exact http_status + cli_exit
      values from the §22 table; no duplicates.
- [ ] `mypy --strict` clean; no `Any` in public signatures.

# Validation

```bash
uv run pytest packages/core/tests/model packages/core/tests/glyph_svg -q
HYPOTHESIS_PROFILE=ci uv run pytest packages/core/tests/glyph_svg/test_roundtrip.py -q
uv run mypy packages/core/src
```

# Dependencies

01, 04 (codepoint formatting helpers may live in charset).

# Non-goals

Fitting math (14), pathops cleanup (14), SVG *rendering* (18/33), service HTTP error envelope
(26).

# Design References

DESIGN §5, §9.4 (format + parser restrictions), §9.5 (warnings), §17.4 (SVG input rules), §22
(registry).
