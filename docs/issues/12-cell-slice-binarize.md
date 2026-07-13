# Title

Ingest S5–S8: cell slicing, illumination flattening, binarization, ink classification

# Summary

Slice the rectified canonical page into per-cell bitmaps, flatten illumination, binarize
(Otsu), despeckle, and classify each cell's ink (empty / ok / warnings) per DESIGN §8.2
S5–S8 and the §9.5 warning taxonomy.

# Context

Output of this stage is the binarized cell bitmap that vectorization consumes — the last
raster stage. Guides printed in the template must reliably vanish here (they are ≤ 20% gray by
§7.1; handwriting is expected substantially darker).

# Scope

`packages/core/src/glyphlab/ingest/cells.py` + tests using corpus pages rectified by 11.

# Detailed Requirements

1. Contract types (defined here; issue 14 consumes them):
   ```python
   @dataclass(frozen=True)
   class CellGeometry:
       codepoint: int
       script_class: Literal["latin", "kana", "punct_ja"]
       cell_ref: tuple[int, int, int]        # (page, row, col)
       box_px: tuple[int, int, int, int]     # inset writing box in canonical-page px (x0, y0, x1, y1)
       guides: GuideGeometry                 # issue 07's per-class guide positions, cell-local px

   @dataclass(frozen=True)
   class CellBitmap:
       geom: CellGeometry
       bitmap: "np.ndarray"                  # bool, cell-local, y-down
       ink_ratio: float
       warnings: list[GlyphWarning]
       failed: bool                          # req 4 component-cap breach; never traced
   ```
   `slice_cells(page: RectifiedPage, sidecar) -> Iterator[tuple[CellGeometry, np.ndarray]]`
   — crop each mapped cell's writing box using issue 07's sidecar-driven `cell_box_px`
   accessor (already inset by 24 px = 2 mm per §8.2 S5; integer px, floor origin / ceil
   extent); skip padding cells.
2. `binarize_cell(cell: np.ndarray, geom: CellGeometry) -> CellBitmap`:
   a. Illumination flattening: `flat = cell / max(GaussianBlur(cell, σ=box/4), 1)` rescaled to
      uint8 (S6).
   b. Otsu threshold (`cv2.threshold(..., THRESH_BINARY_INV | THRESH_OTSU)`) → ink=1.
   c. Morphological open 3×3 (1 iter); remove connected components with area < 9 px
      (`cv2.connectedComponentsWithStats`).
   d. Record `touches_border`: any surviving component with a pixel on the crop boundary.
3. Ink classification inside `binarize_cell` per §8.2 S8: ink ratio r < 0.005 → empty
   (`bitmap=None`-equivalent: represented as CellBitmap with `ink_ratio` and an
   `is_empty` property r < 0.005); r > 0.40 → OK + `LARGE_INK_BLOB` warning;
   0.005 ≤ r < 0.015 → OK + `LOW_INK`; else OK. Attach `TOUCHES_BORDER` when flagged
   in 2d.
3b. Trace-work bound (§17.3 T5): after cleanup, if the connected-component count exceeds
   **64**, set `failed=True` (cell reported `failed`, never passed to the vectorizer) —
   this is the designed bound on tracing work for adversarial noise cells.
4. Guide-suppression guarantee: a test renders an *unfilled* corpus page (issue 09's
   `fill_fraction=0.0`), runs S5–S8, and asserts **every** cell classifies empty — i.e.
   printed guides+labels never survive binarization. (Labels are outside the writing box
   by §7.1; this test also catches inset regressions.)
5. Determinism: pure numpy/cv2 ops, no RNG.
6. Performance: 49 cells of one page ≤ 1.5 s total on CI (a sub-budget within §21's
   15 s/page total).

# Acceptance Criteria

- [ ] Unfilled-page test: 49/49 cells empty.
- [ ] `clean-scan` filled page: every manifest-inked cell classified OK; every seeded-empty
      cell empty; zero missed/spurious.
- [ ] `phone-dark` (if it rectifies per issue 11 golden): ≥ 95% agreement with manifest;
      pinned exact number as golden.
- [ ] A synthetic cell with a 1-px dust speck grid classifies empty (despeckle works).
- [ ] Adversarial 1-px checkerboard cell → `failed=True` (component cap), never traced.

# Validation

```bash
uv run pytest packages/core/tests/ingest/test_cells.py -q
```

# Dependencies

09, 11.

# Non-goals

Vectorization (13), em fitting (14), any UI surfacing of warnings (23/33/42).

# Design References

DESIGN §8.2 S5–S8, §9.5 (warning codes), §7.1 (guides/labels geometry), §21 (budgets).
