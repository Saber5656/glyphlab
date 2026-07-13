# Title

Font assembly: TTF + WOFF2 via fontTools.fontBuilder

# Summary

Build the final font from accepted/included glyph SVGs: cubic→quadratic conversion, all
required tables with the exact DESIGN §10.3 metrics, naming per §10.4, synthesized glyphs,
reproducible binaries, and WOFF2 export.

# Context

Output correctness here is the product's deliverable. Everything is already validated
geometry; this issue is table bookkeeping done exactly once, exactly right.

# Scope

`packages/core/src/glyphlab/fontbuild/{builder.py,naming.py}` + tests. Adds core deps:
`fonttools[woff]` (brotli via extra).

# Detailed Requirements

1. `build_font(project: ProjectConfig, glyphs: dict[int, tuple[GlyphOutline, int]], charset:
   CharsetSpec, out_dir: Path) -> BuildResult` where
   `BuildResult = {ttf_path: Path, woff2_path: Path, glyph_count: int,
   missing: list[str]}` — `missing` = drawn charset codepoints absent from `glyphs`, as
   sorted `U+XXXX` strings. Output filenames per §10.1:
   `{family_name}-v{project.version}.ttf` / `.woff2` inside `out_dir` (overwritten
   unconditionally). A key in `glyphs` outside the charset → `E_VALIDATION`.
   Input selection (which statuses) is the caller's job (24/32); builder takes resolved
   glyphs.
   Security note (§17.3 T8): builder output is NOT a shippable artifact until the issue-17
   QA gate has passed — callers must run QA before exposing files to users.
2. Glyph set assembly:
   - `.notdef`: open rectangle, 50-unit stroke: outer (100,−120)–(500,780), inner inset 50;
     advance 600.
   - Synthesized: U+0020 adv 500, U+3000 adv 1000 (from `SYNTHESIZED_ADVANCES`), empty
     outlines — only when in charset.
   - Drawn glyphs: from input dict; read via issue-06 parser happens in the caller; builder
     receives outlines (keeps builder pure).
   - Glyph names: AGLFN where defined, else `uniXXXX` (4-hex, uppercase; 5–6 hex for
     supplementary — not in v1 charsets).
3. Curve conversion: `from fontTools.pens.cu2quPen import Cu2QuPen` wrapping a
   `fontTools.pens.ttGlyphPen.TTGlyphPen`, max error 1.0 unit; reverse contour direction
   as required for TrueType (clockwise outer).
4. Tables (fontBuilder, UPM 1000): `head` (flags 0b11, lowestRecPPEM 7; `created`/`modified`
   from `SOURCE_DATE_EPOCH` env if set else current time), `hhea`/`OS/2` per §10.3 exactly
   (winAscent 880/winDescent 120, typo 880/−120/0, fsType 0, ulCodePageRange1 bits {0, 17}
   for `ja-basic-v1`, {0} for `ascii`; xAvgCharWidth computed), `cmap` formats 4 + 12,
   `hmtx`, `post` v2.0, `maxp`, `gasp` (rangeMaxPPEM 0xFFFF → behavior 0b1111), `name`
   with exactly these strings (no other inputs exist — DESIGN §10.4):
   - ID 0: `Copyright {build_year} the font author. Generated with glyphlab.`
   - ID 1: `{family_name}` · ID 2: `Regular` · ID 3: `glyphlab:{family_name}:{version}`
   - ID 4: `{family_name} Regular` · ID 5: `Version {version}.000`
   - ID 6: `{family_name with spaces removed}-Regular`
   - ID 11: `https://github.com/Saber5656/glyphlab`
   - ID 13: `The font and the handwriting it embodies belong to the person who wrote it.
     glyphlab claims no rights over generated fonts.`
   - ID 14: `https://github.com/Saber5656/glyphlab`
   `ulCodePageRange1` rule (works for presets AND custom charsets): bit 0 always; bit 17
   added iff the charset contains any `kana`/`punct_ja` char.
5. WOFF2: `font.flavor = "woff2"; font.save(woff2_path)` after TTF save.
6. Reproducibility: with `SOURCE_DATE_EPOCH` set, two builds of identical inputs are
   byte-identical (test asserts SHA equality).
7. `GlyphCompleter` entry-point group `glyphlab.completers` registered in core pyproject
   (empty; §9.6) — the only v1 nod to completion.
8. Tests: golden build fixture `tests/fontbuild/conftest.py::golden_font` — codepoints
   exactly {U+0041 'A', U+002E '.', U+3042 'あ', U+30A2 'ア', U+3002 '。'} with hand-built
   box/triangle outlines + synthesized U+0020/U+3000 (charset: a tiny custom CharsetSpec
   fixture) — the same fixture issues 17/18 reuse. Assert with `fontTools.ttLib.TTFont`:
   cmap covers exactly the expected set; hmtx advances (kana/punct 1000, U+0020 500,
   U+3000 1000); OS/2/hhea/head fields exact; all name IDs equal the strings above; glyph
   order `.notdef` first then ascending; WOFF2 loads and equals TTF glyph count; full
   table access: `TTFont(path, lazy=False)` then read every table without exception.

# Acceptance Criteria

- [ ] Byte-reproducible under `SOURCE_DATE_EPOCH=1700000000`.
- [ ] All table assertions green; `TTFont(path, lazy=False)` reads every table without
      exception.
- [ ] Curve conversion error bound test: max deviation sampled over 200 points ≤ 1.5 units.
- [ ] fsType == 0 (installable); `missing` list correct when a drawn glyph is withheld.

# Validation

```bash
uv run pytest packages/core/tests/fontbuild -q
SOURCE_DATE_EPOCH=1700000000 uv run pytest packages/core/tests/fontbuild/test_repro.py -q
```

# Dependencies

04, 05, 06.

# Non-goals

QA gate (17), proof sheet (18), OpenType features/kerning (v2 D5), vertical metrics tables
(NG7), hinting (NG9).

# Design References

DESIGN §10 (all), §6.1 (synthesized), §9.6 (completer hook), §5 (UPM/metrics).
