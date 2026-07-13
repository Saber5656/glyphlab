# Title

Path cleanup & em-space fitting (cell pixels → font units)

# Summary

Implement DESIGN §9.2–§9.3: skia-pathops union/cleanup of traced contours, then the
deterministic mapping from cell-pixel space into the em square — per-script-class anchoring,
sidebearings/advance rules, clamping, and warnings.

# Context

This stage makes handwriting into *typographically consistent* glyphs: shared baseline for
Latin, full-width squares for kana. All numbers are fixed by design (§9.3) so results are
reproducible and testable.

# Scope

`packages/core/src/glyphlab/fit/{cleanup.py,fitting.py}` + tests. Adds core dep
`skia-pathops`.

# Detailed Requirements

1. `cleanup.py`: `clean_outline(contours: list[Contour], *, min_contour_area: float) ->
   tuple[GlyphOutline, list[GlyphWarning]]` — convert to a pathops `Path`, `union`
   (nonzero), convert back to cubic contours; drop resulting contours with
   |signed area| < `min_contour_area` (fitting calls this post-transform with `40.0`
   font-units²); emit `TINY_CONTOURS_REMOVED` if any dropped. Signed area computed
   deterministically: flatten each contour with fixed tolerance 0.5 units → shoelace
   formula on the polyline. (skia-pathops works on quads/cubics natively; preserve cubics
   via its `Path` segment API.)
2. `fitting.py`: `fit_glyph(bitmap_contours: list[Contour], geom: CellGeometry, char:
   CharDef, cell_warnings: list[GlyphWarning]) -> Glyph` implementing §9.3 exactly
   (`CellGeometry` is issue 12's contract type — box px rect, script class, guide
   positions):
   - Build the cell-space→em-space affine map (uniform scale + translation, y-flip):
     `latin`: cell baseline line (30% from box bottom) ↦ y=0; x-height line (62%) ↦ y=460 ⇒
     scale = 460 / (0.32 × box_px_height); `kana`/`punct_ja`: square guide bottom ↦ −120,
     top ↦ 880 ⇒ scale = 1000 / (0.88 × box_px_height).
   - Apply map to contours, then `clean_outline` with `min_contour_area=40`.
   - Horizontal metrics: `latin` → advance = 60 + ink_width + 60, LSB 60 (translate ink to
     x=60); `kana`/`punct_ja` → advance = 1000, ink centered: translate so bbox center x =
     500. Advance floor 120 (§9.3).
   - Clamp & warn: if the mapped ink bbox has y outside [−250, 1000], uniformly scale
     down about the anchor point — latin: (bbox center x, 0); kana/punct_ja: (500, 380) —
     by exactly the factor that brings the violating extreme onto the boundary, then
     recompute horizontal metrics per the rules above (latin advance from the new ink
     width; kana advance stays 1000 with re-centering), and add `OFF_GUIDE`.
   - Round all final coordinates to integers (font units); advance to int.
3. `Glyph.warnings` = `cell_warnings` (from issue 12, e.g. `LOW_INK`) + fitting warnings
   (`OFF_GUIDE`, `TINY_CONTOURS_REMOVED`); status `AUTO`.
4. Property tests (hypothesis): random ink bboxes → advance ≥ 120; kana advance always
   1000; latin LSB always 60 when unclamped; produced contours closed; mapping
   orientation: x is order-preserving (x1 < x2 ⇒ X1 < X2) and y is order-reversing
   (bitmap y-down → font y-up: y1 < y2 ⇒ Y1 > Y2).
5. Golden tests: 5 corpus glyph bitmaps (あ, A, x, 。, ー) through trace+fit; assert stable
   integer bboxes/advances (snapshot with exact values).

# Acceptance Criteria

- [ ] Property + golden suites green and deterministic across platforms (integer outputs).
- [ ] A deliberately overscaled synthetic contour triggers `OFF_GUIDE` and fits afterwards.
- [ ] Union removes overlap: two overlapping circles → single outer contour.
- [ ] `mypy --strict` clean.

# Validation

```bash
uv run pytest packages/core/tests/fit -q
uv run mypy packages/core/src
```

# Dependencies

06, 12 (CellGeometry/warnings), 13 (contour input; can stub with hand-built contours to start).

# Non-goals

Kerning, per-glyph user adjustments (v2), hinting (NG9), font assembly (16).

# Design References

DESIGN §9.2, §9.3, §9.5, §5 (coordinate system), §7.1 (guide fractions).
