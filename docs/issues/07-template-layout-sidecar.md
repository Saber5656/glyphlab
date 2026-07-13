# Title

Template layout model & `template.json` sidecar

# Summary

Implement the pure-geometry side of templates: compute page/cell layout for a charset from the
DESIGN §7.1 constants, and read/write the versioned `template.json` sidecar (§7.2) that ingest
later uses as the sole cell→codepoint authority.

# Context

Splitting geometry (this issue) from PDF drawing (08) lets ingest and the synthetic corpus (09)
depend on exact numbers without any PDF library, and makes layout unit-testable.

# Scope

`packages/core/src/glyphlab/template/{layout.py,sidecar.py}` + tests. No PDF rendering.

# Detailed Requirements

1. `layout.py` constants exactly per §7.1 (all mm, floats): page 210×297, margin 12, header
   band top 12→32, content area x 12→198 / y 36→283, marker side 14.0 (corner positions per
   §7.1 table), grid origin (12, 54), cell box 25.0, label strip 3.0, gap 1.5, cols 7,
   rows 7 (49 cells/page), canonical raster 2481×3508 px (A4@300dpi), `MM_TO_PX = 300/25.4`.
2. `compute_layout(charset: CharsetSpec) -> TemplateLayout`:
   - Cells = `charset.drawn_chars()` in charset order (ascending codepoint), row-major,
     49/page; last page padded with `None` cells (rendered empty, never mapped).
   - Page count = ceil(drawn/49); **assert page count ≤ 12** (DICT_4X4_50 marker budget);
     raise `E_VALIDATION` otherwise (guards future kanji presets against silent overflow;
     custom charsets are already capped at 500 drawn per §17.4).
   - Marker IDs for page k: `(4k, 4k+1, 4k+2, 4k+3)` = (TL, TR, BR, BL).
   - Marker geometry: markers sit in the content-area corners **outside** the cell grid
     (§7.1); homography anchors = content-area corners (12, 36), (198, 36), (198, 283),
     (12, 283). Provide mm and canonical-px accessors: `marker_rect_mm(page, which)`,
     `content_corners_px()`, `cell_box_px(page, row, col)` inset by 2 mm equivalent = 24 px
     (§8.2 S5), `guide_lines_px(cell)` per script class (§7.1).
3. In-cell guide geometry API (needed by 08 and 14): for `latin` cells `baseline_frac = 0.30`,
   `xheight_frac = 0.62` from box bottom; for `kana`/`punct_ja` a centered square
   `0.88 * box`. Expose as pure functions of the cell box.
4. `sidecar.py`: dataclasses mirroring §7.2 JSON; `write_sidecar(path, layout, template_id,
   charset)` and `read_sidecar(path, expected_charset: CharsetSpec | None = None)`.
   Validation on read is **internal consistency only** (never equality with current layout
   constants — old printed sheets must keep working after future layout changes; geometry
   is read FROM the sidecar everywhere downstream): schema field == `"glyphlab.template/1"`;
   aruco ids == `(4k..4k+3)` for the page's index; codepoints unique across pages; grid
   numbers positive and grid fits inside the content rect. When `expected_charset` is
   provided (the ingest path), additionally require `charset_id`/`charset_version` match
   and every cell codepoint ∈ expected drawn set — mismatch raises a `GlyphlabError`
   subclass with code `E_TEMPLATE_MISMATCH` (base class from issue 06; the page-≤12
   assertion in `compute_layout` likewise raises code `E_VALIDATION`).
5. Determinism & serialization contract: `json.dumps(payload, sort_keys=True, indent=2,
   ensure_ascii=False)` + trailing newline; all floats pre-rounded to 2 decimals on write.
   Same charset + template_id ⇒ byte-identical file; `write(read(p)) == p` byte-for-byte.

# Acceptance Criteria

- [ ] `ja-basic-v1` → 6 pages, pages 0–4 full (49), page 5 has 31 cells + 18 padding.
- [ ] First cell of page 0 = U+0021 (`!`; U+0020 not drawn); last drawn cell = U+30FC per
      ascending preset order.
- [ ] Grid never overlaps marker rects (geometry unit test comparing rect intersections).
- [ ] Sidecar round-trip byte-identical; tampered sidecar (duplicate codepoint, marker id
      mismatch) rejected.
- [ ] `cell_box_px` values consistent with mm values × 300/25.4 within 0.5 px.

# Validation

```bash
uv run pytest packages/core/tests/template -q
uv run python -c "
from glyphlab.charset import get_preset
from glyphlab.template.layout import compute_layout
l = compute_layout(get_preset('ja-basic-v1'))
print(l.page_count, len(l.pages[5].cells_with_chars()))"
# expect: 6 31
```

# Dependencies

04, 06 (GlyphlabError base + error codes).

# Non-goals

PDF drawing (08), ArUco bitmap generation (08), rectification (11).

# Design References

DESIGN §7.1 (geometry constants), §7.2 (sidecar), §8.2 S5 (inset), §6.1 (drawn cells).
