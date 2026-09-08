# glyphlab — v1 Design

- Status: v1 canonical design (source of truth, together with `docs/decisions/` ADRs)
- Date: 2026-07-08
- Language policy: repository docs and code identifiers are English; the web UI ships
  Japanese-first user-facing strings (§16.5)
- Derived artifacts: `docs/ISSUE_PLAN.md`, `docs/issues/*.md`, GitHub Issues

---

## 1. Product definition

**glyphlab** turns handwriting into an installable font. The user prints a template PDF, writes
each character in its cell with a pen, scans or photographs the pages, and glyphlab produces a
TTF/WOFF2 font of their handwriting.

One deterministic pipeline, three delivery surfaces sharing the same core library:

1. **Python library** (`glyphlab` on PyPI) — the pipeline itself.
2. **CLI** — local-first, privacy-maximal workflow for technical users.
3. **Hosted web service** — no-install workflow: create an anonymous project, upload scans,
   review glyphs, download the font. Self-hostable via Docker; deploy-ready for Fly.io.

### 1.1 Personas

| Persona | Surface | Needs |
|---|---|---|
| P1: Japanese casual user | Hosted web | Wants their handwriting as a font for documents/social media without installing anything. Non-technical. Uses a phone camera, not a scanner. |
| P2: Technical user / font tinkerer | CLI | Wants local control, editable intermediates (SVG), reproducible builds, no data leaving the machine. |
| P3: Self-hoster | Docker | Runs the service for family/community; needs one-command bring-up and clear ops docs. |

### 1.2 User journey (hosted, happy path)

1. Open site → "Create project" → choose charset preset → receives project URL containing an
   unguessable token (shown once, stored in browser).
2. Download template PDF (6 pages for the default Japanese preset). Print at 100% scale.
3. Handwrite; photograph each page; upload photos.
4. Service detects the page via fiducial markers, rectifies, slices cells, vectorizes; user sees
   a glyph grid with per-glyph status.
5. User rejects bad glyphs (rewrites and re-uploads that page if desired).
6. "Build font" → downloads `.ttf` (install) and `.woff2` + HTML proof sheet.
7. Project auto-deletes after the retention period.

The CLI journey is identical with `glyphlab new/template/ingest/status/build` and a local
project directory instead of steps 1/7.

---

## 2. Scope

### 2.1 v1 goals

- G1: Paper-template capture with robust phone-photo rectification (fiducial markers).
- G2: Charset presets: `ascii`, `kana`, and default `ja-basic-v1` (§6).
- G3: Deterministic pipeline producing valid TTF + WOFF2 passing the fontbakery universal
  profile QA gate (§11).
- G4: CLI covering the full workflow locally, with user-editable SVG glyph intermediates.
- G5: Hosted service: anonymous token projects, upload→review→build→download, auto-retention.
- G6: Web UI (Japanese-first) for the hosted flow.
- G7: Deploy-ready: Docker image(s), docker-compose self-host, Fly.io config + runbook.
  Actual production operation (domain, accounts, secrets) is a human task after v1.
- G8: Security engineered in: threat model (§17), enforced limits, secure defaults.

### 2.2 v1 non-goals

- NG1: Browser/stylus handwriting input (v2; input adapter interface reserved, §8.1).
- NG2: Kanji presets and large-set campaign management (sheet progress tracking beyond one
  charset's pages).
- NG3: AI completion of missing glyphs (v2 extension hook only, §9.6).
- NG4: OpenType ligatures, contextual alternates, glyph variants/randomization.
- NG5: Accounts, login, project listing; email; payments.
- NG6: Per-glyph editing in the web UI (accept/reject only; editing is CLI+SVG).
- NG7: Vertical writing metrics (`vmtx`/`vhea`) and fullwidth Latin (U+FF01–FF5E).
- NG8: Multi-instance horizontal scaling of the service (single machine pinned, ADR-005).
- NG9: Hinting (TTF ships unhinted; modern rasterizers make this acceptable for v1).

### 2.3 v2 deferred (explicitly designed-for, not built)

- D1: Digital ink input adapter (browser canvas / iPad) producing `GlyphSource` objects (§8.1).
- D2: Kanji charset presets (JIS level 1 subset) + campaign/progress UX.
- D3: AI glyph completion behind `GlyphCompleter` interface (§9.6).
- D4: Accounts layered *on top of* token projects (schema keeps `projects` self-contained).
- D5: OpenType features (`calt` randomization, ligatures), glyph variants.
- D6: Web-based glyph editor; local web UI mode (`glyphlab web`).
- D7: Postgres + external job queue for multi-instance scaling.
- D8: English/multilingual UI.

### 2.4 Known unknowns (tracked in ISSUE_PLAN §8)

- KU-1: potrace parameter tuning for pen-width variance (turdsize/alphamax defaults may need
  calibration against real handwriting samples).
- KU-2: `cv2.aruco` API behavior under OpenCV 5.x wheels (API used is the 4.7+ `ArucoDetector`;
  smoke test in CI).
- KU-3: Phone-photo robustness envelope (glare, shadow, low light) — acceptance thresholds may
  move after real-device testing.
- KU-4: fontbakery universal-profile findings on generated fonts — the accepted-findings
  allowlist will be calibrated on the first golden build.
- KU-5: HEIC decode reliability across pillow-heif versions/platforms.
- KU-6: PyPI/name-squatting — register `glyphlab` at first release.

---

## 3. System architecture

```
                    ┌─────────────────────────────────────────────┐
                    │                 webui (TS/React SPA)        │
                    │  create/open · upload · review · build/DL   │
                    └──────────────────┬──────────────────────────┘
                                       │ HTTPS JSON (OpenAPI, §15)
┌───────────────┐   ┌──────────────────▼──────────────────────────┐
│ glyphlab CLI  │   │ service (FastAPI)                           │
│ (typer)       │   │  auth (token) · limits · endpoints          │
└───────┬───────┘   │  ┌──────────────┐  ┌──────────────────────┐ │
        │           │  │ jobs worker  │  │ retention sweeper    │ │
        │           │  │ (in-process) │  │ (periodic)           │ │
        │           │  └──────┬───────┘  └──────────┬───────────┘ │
        │           └─────────┼─────────────────────┼─────────────┘
        │                     │                     │
┌───────▼─────────────────────▼─────────────────────▼─────────────┐
│ glyphlab core library (Python)                                  │
│ charset · template · ingest(image→cells) · vectorize · fit      │
│ fontbuild · qa · report · project store                         │
└───────┬─────────────────────────────────────────────────────────┘
        │                     │                     │
   local project dir     SQLAlchemy DB         ObjectStore
   (CLI, §12)            (SQLite→Postgres)     (local disk→S3)
```

Rules:

- The service **never** reimplements pipeline logic; it orchestrates core-library calls in jobs.
- The core library has **no** knowledge of HTTP, DB, or object storage; it works on paths/bytes
  and in-memory models.
- All processing is synchronous pure-ish functions; concurrency lives only in the service worker.

---

## 4. Repository layout (monorepo)

```
glyphlab/
├── pyproject.toml              # uv workspace root
├── packages/
│   ├── core/                   # PyPI package "glyphlab": library + CLI
│   │   ├── pyproject.toml
│   │   └── src/glyphlab/
│   │       ├── charset/        # §6
│   │       ├── template/       # §7
│   │       ├── ingest/         # §8  (imaging, page detect, cells)
│   │       ├── vectorize/      # §9.1–9.3
│   │       ├── fit/            # §9.4–9.5 (em fitting, metrics)
│   │       ├── fontbuild/      # §10
│   │       ├── qa/             # §11
│   │       ├── report/         # §11.3
│   │       ├── project/        # §12 (local store, config)
│   │       └── cli/            # §13
│   └── service/                # package "glyphlab-service" (not on PyPI)
│       ├── pyproject.toml
│       └── src/glyphlab_service/
│           ├── app.py settings.py auth.py limits.py
│           ├── db/  (models.py, migrations/)
│           ├── store/ (object store impls)
│           ├── jobs/ (queue, worker, handlers)
│           └── api/  (routers)
├── webui/                      # Vite + React + TS SPA
├── deploy/                     # Dockerfile, docker-compose.yml, fly.toml, runbook
└── docs/                       # this file, ADRs, issues, research
# The synthetic scan corpus generator (§18.2) lives in packages/core/tests/corpus/
# (test-support code, never shipped in the wheel).
```

Python ≥ 3.11. Tooling: `uv` (workspace, lock), `ruff` (lint+format), `mypy --strict` on core,
`pytest`. Node ≥ 20 for webui.

---

## 5. Core domain model

Coordinate system: font units, **UPM = 1000**; y-up; origin at baseline/left-sidebearing.
Vertical metrics: ascender = **880**, descender = **−120**, typo/hhea/win metrics all derived
from these (§10.3).

```python
# glyphlab/charset/model.py
@dataclass(frozen=True)
class CharDef:
    codepoint: int
    script_class: Literal["latin", "kana", "punct_ja"]   # drives cell guides & fitting
    drawn: bool                                          # False → synthesized (space)

@dataclass(frozen=True)
class CharsetSpec:
    charset_id: str          # e.g. "ja-basic-v1"
    version: int             # bump on any change; embedded in template sidecar
    chars: tuple[CharDef, ...]

# glyphlab/model.py — shared geometry & glyph types
@dataclass(frozen=True)
class Point:
    x: float
    y: float

@dataclass(frozen=True)
class CubicSegment:          # cubic Bézier: p1 --(c1, c2)--> p2
    p1: Point; c1: Point; c2: Point; p2: Point

@dataclass(frozen=True)
class Contour:               # closed: first point == last segment end
    segments: tuple[CubicSegment, ...]

class GlyphStatus(StrEnum):
    MISSING = "missing"      # no source yet
    AUTO = "auto"            # extracted, not human-reviewed
    ACCEPTED = "accepted"    # human approved (or CLI --auto-accept)
    REJECTED = "rejected"    # human rejected; excluded from build

@dataclass
class Glyph:
    codepoint: int
    status: GlyphStatus
    outline: GlyphOutline | None   # cubic contours in font units
    advance: int | None            # font units
    warnings: list[GlyphWarning]   # §9.5
    source: GlyphSourceRef | None  # GlyphSourceRef(upload: str, cell: int)

@dataclass(frozen=True)
class GlyphOutline:
    contours: tuple[Contour, ...]  # Contour = tuple of cubic segments, closed
```

`GlyphWarning` codes: `LOW_INK`, `TOUCHES_BORDER`, `TINY_CONTOURS_REMOVED`, `LARGE_INK_BLOB`,
`OFF_GUIDE` (definitions in §9.5).

---

## 6. Charsets

### 6.1 Presets (exact contents)

| Preset | Contents | Encoded glyphs | Drawn cells |
|---|---|---|---|
| `ascii` | U+0020–U+007E | 95 | 94 (U+0020 synthesized) |
| `kana` | Hiragana U+3041–U+3096 (86); Katakana U+30A1–U+30FA (90); U+30FC; U+3001, U+3002, U+300C, U+300D, U+30FB; U+3000 | 183 | 182 (U+3000 synthesized) |
| `ja-basic-v1` (default) | union(`ascii`, `kana`) | 278 | 276 |

Note: drawn cells for `ja-basic-v1` = 94 + 182 = 276 (space and ideographic space synthesized).
Canonical ordering: a `CharsetSpec` stores chars in **strictly ascending codepoint order**
(so `ja-basic-v1` runs U+0020…U+007E, U+3000…U+3002, U+3041…U+3096, U+30A1…U+30FC); template
cell order is the drawn subsequence of that order.

`script_class` assignment: U+0020–U+007E → `latin`; U+3041–U+3096, U+30A1–U+30FA, U+30FC →
`kana`; U+3000–U+3002, U+300C, U+300D, U+30FB → `punct_ja`.

Synthesized glyphs: U+0020 advance = **500**; U+3000 advance = **1000**; both empty outlines.
`.notdef` is generated as a 50-unit-stroke open rectangle, advance 600.

### 6.2 Rules

- Presets are code (`glyphlab/charset/presets.py`), not user files; a preset's `(charset_id,
  version)` is immutable once released — any change requires a version bump.
- The hosted service exposes **presets only** (no custom charsets server-side in v1 — parser
  attack-surface reduction). The CLI additionally accepts a custom charset TOML (schema in
  §12.2, limits in §17.4: ≤ 500 drawn chars) for local use.
- Every template, project, and font embeds the `(charset_id, version)` it was created from;
  ingest **must** refuse a scan whose template sidecar charset does not match the project.

---

## 7. Paper template

### 7.1 Page geometry (A4 portrait, millimetres)

| Element | Value |
|---|---|
| Page | 210 × 297 |
| Margins | 12 all around |
| Header band | y: 12–32 from top; contains: title, `charset_id@version`, page `k/N`, human instructions (ja), 100%-scale check ruler (50 mm bar) |
| Content area | x: 12–198, y: 36–283 (the region the fiducials delimit) |
| Fiducials | 4 × ArUco `DICT_4X4_50`, marker side **14 mm**, one in each corner of the content area — TL (12, 36), TR (184, 36), BR (184, 269), BL (12, 269) as (x, y) of the marker's top-left, i.e. marker squares span x 12–26 / 184–198 and y 36–50 / 269–283. Page *k* (0-based) uses marker IDs `4k, 4k+1, 4k+2, 4k+3` (TL, TR, BR, BL) → max 12 pages. Homography anchors = the content-area corners (12, 36), (198, 36), (198, 283), (12, 283) = the markers' outermost corners |
| Cell grid region | x: 12–198, y: **54–259** — strictly between the top and bottom marker bands (≥ 4 mm clearance from markers; markers never overlap cells) |
| Cells | **7 columns × 7 rows = 49 cells/page**; cell = **25 × 25 mm writing box** + 3 mm label strip above (cell pitch 25 + 3 + 1.5 gap = 29.5 mm vertical, 25 + 1.5 = 26.5 mm horizontal). Grid occupies 184 × 205 mm — fits the region with slack |
| Cell label | target character (11 pt, 45% gray) + `U+XXXX` (6 pt) printed in the label strip — **outside** the writing box so labels never contaminate extraction |
| In-cell guides | `latin`: baseline rule at 30% from bottom, x-height rule at 62% from bottom, both 20% gray 0.2 mm. `kana`/`punct_ja`: centered square guide at 88% of box size, 20% gray dashed |

Geometry sanity: rows 7 × 28 mm + 6 × 1.5 mm = 205 mm ≤ 205 mm region height; cols 7 × 25 mm
+ 6 × 1.5 mm = 184 mm ≤ 186 mm region width.

`ja-basic-v1`: 276 cells → **6 pages** (5 × 49 + 31; last page padded with empty unused cells).
Cell order: charset order (ascending codepoint, drawn only), row-major, left→right,
top→bottom. Custom charsets (CLI-only) are capped at **500 drawn chars** = 11 pages, inside
the 12-page marker budget.

### 7.2 Template sidecar (`template.json`, schema v1)

```json
{
  "schema": "glyphlab.template/1",
  "template_id": "uuid4",
  "charset_id": "ja-basic-v1",
  "charset_version": 1,
  "pages": [
    {
      "index": 0,
      "aruco_ids": [0, 1, 2, 3],
      "content_mm": {"x0": 12.0, "y0": 36.0, "x1": 198.0, "y1": 283.0, "marker": 14.0},
      "grid_mm": {"x0": 12.0, "y0": 54.0, "cell": 25.0, "label_h": 3.0, "gap": 1.5, "cols": 7, "rows": 7},
      "cells": [{"row": 0, "col": 0, "codepoint": 33}]
    }
  ]
}
```

The sidecar is the **only** authority for cell→codepoint mapping during ingest; the pipeline
never OCRs labels. The PDF and sidecar are generated by the same function call and share the
`template_id` (printed in the header as an 8-char prefix for human cross-checking).
Known limitation: markers encode only the page index, so sheets printed from an older
template of the same charset are geometrically indistinguishable after regeneration —
regenerating a template therefore requires reprinting; the CLI must warn accordingly
(issue 21).

### 7.3 Security note

Template generation consumes only trusted inputs (preset charsets, project name string). The
project name is rendered onto the PDF — it must be length-limited (≤ 64 chars) and control
characters stripped (§17.4 input table).

---

## 8. Ingest pipeline (scan → per-cell bitmaps)

### 8.1 Input adapter boundary

```python
class GlyphSource(Protocol):
    """v1: ScanPageSource. v2: DigitalInkSource (browser strokes)."""
    def iter_cells(self) -> Iterator[tuple[CellRef, np.ndarray]]: ...  # binarized cell bitmaps
```

Everything downstream of this interface (vectorize → fit → build) is input-agnostic. This is
the reserved v2 seam (NG1/D1).

### 8.2 Stages, contracts, failure codes

Working raster: pages are rectified to a canonical **2481 × 3508 px** (A4 @ 300 dpi) grayscale
image; all geometry derives from template mm × 300/25.4.

| # | Stage | Input → Output | Failure code (§22) |
|---|---|---|---|
| S1 | Decode & sanitize | file bytes → grayscale uint8 ndarray. Formats: JPEG/PNG/HEIC (magic-byte sniff via `sniff_format`). Enforce: size ≤ 12 MiB, pixels ≤ 36 MP (header-checked before full decode), `Image.MAX_IMAGE_PIXELS` set, EXIF orientation applied, alpha flattened to white, longest side downscaled to ≤ 4500 px | `E_IMG_FORMAT`, `E_IMG_TOO_LARGE`, `E_IMG_DECODE` |
| S2 | Marker detection | grayscale → ArUco corners (`ArucoDetector`, `DICT_4X4_50`). Detection ladder: original → CLAHE-enhanced → 1.5× upscaled (when longest side < 3000 px), stopping at first success | `E_PAGE_NO_MARKERS` (no page group with 4 corner roles) |
| S3 | Page identification | marker IDs → page index (`id // 4`). Ambiguity rule: ≥ 2 pages with ≥ 2 detected markers each → `E_PAGE_AMBIGUOUS`; a single stray marker from another page is logged in diagnostics and ignored. The winning page must exist in the template sidecar | `E_PAGE_AMBIGUOUS`, `E_PAGE_UNKNOWN` |
| S4 | Rectification | 4 marker outer corners → homography → canonical raster. Quality gates: reprojection error ≤ 3 px; sharpness (variance of Laplacian on grid region) ≥ threshold | `E_PAGE_WARPED`, `E_PAGE_BLURRY` |
| S5 | Cell slice | canonical raster + sidecar geometry → per-cell crop, inset by **2 mm** equivalent (24 px) to exclude cell borders |  |
| S6 | Illumination flattening | cell → cell ÷ Gaussian-blurred background (σ ≈ cell/4), rescaled |  |
| S7 | Binarize & clean | Otsu threshold; morphological open (3×3); remove components < **9 px²**; border-touching component check | per-cell flag, not fatal |
| S8 | Ink classification | ink ratio r = ink px / cell px. r < 0.5% → cell `EMPTY`; r > 40% → `LARGE_INK_BLOB` warning; else OK |  |

Per-page output: `PageIngestResult { page_index, cells: [CellResult], metrics }` where
`CellResult = {codepoint, status: empty|extracted, bitmap_ref, warnings[]}`. Page-level failures
(S1–S4) fail the whole upload with one code; cell-level issues never fail the page.

Determinism: given identical bytes and config, every stage must produce identical output
(fixed seeds; no wall-clock dependence). This is load-bearing for golden tests (§18.2).

### 8.3 Re-ingest semantics

Re-uploading a page overwrites glyphs whose status is `MISSING`/`AUTO`/`REJECTED`; glyphs with
status `ACCEPTED` are **never** silently overwritten (CLI: `--force` flag; service: reject the
overwrite for accepted cells and report which were skipped).

---

## 9. Vectorization & glyph construction

### 9.1 Engine interface (ADR-004)

```python
class VectorizerEngine(Protocol):
    name: str
    def trace(self, bitmap: np.ndarray, opts: TraceOpts) -> list[Contour]: ...
```

- `PotraceBinaryEngine`: runs the `potrace` executable via `subprocess.run` with a fixed argv
  (never shell), stdin/stdout pipes, 10 s timeout: `potrace --backend svg --turdsize 2
  --alphamax 1.0 --opttolerance 0.2 --unit 10 -` and parses the SVG paths. Binary resolved from
  `GLYPHLAB_POTRACE_PATH` env or `PATH`; version logged.
- `PotracerEngine`: pure-Python `potracer` (optional extra `glyphlab[trace]`), same parameters.
- Selection: binary if available else potracer else `E_TRACE_UNAVAILABLE` with install hint.
- Output normalized to cubic Bézier contours in cell-pixel space.

### 9.2 Path cleanup

1. `skia-pathops` union of all contours (fixes self-overlaps, sets nonzero orientation).
2. Drop contours with |area| < 40 font-units² after scaling.
3. Record `TINY_CONTOURS_REMOVED` warning when anything was dropped.

### 9.3 Cell-space → em-space fitting

The template geometry makes this deterministic (no per-glyph baseline detection):

| script_class | Mapping |
|---|---|
| `latin` | Cell baseline rule (30% from box bottom) → y = 0; cell x-height rule (62%) → y = 460. Scale = uniform, defined by these two anchors (i.e. 32% of box height ↦ 460 units). x: ink left edge → LSB = 60; advance = 60 + ink width + 60. |
| `kana`, `punct_ja` | Cell square guide maps to em square: guide bottom → y = −120, guide top → y = 880 (uniform scale). x: ink centered in advance = 1000. LSB derived. |

Additional rules: latin space advance 500 (§6.1); glyphs whose scaled ink exceeds y ∈ [−250,
1000] are clamped-with-warning `OFF_GUIDE`; advance minimum 120 (punctuation like `.`).

### 9.4 Glyph SVG intermediate (user-editable, canonical for build)

Each extracted glyph is persisted as a standalone SVG (one file per codepoint, §12.1):

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -880 1000 1000"
     data-glyphlab="glyph/1" data-codepoint="U+3042" data-advance="1000">
  <path d="M ... Z" fill="black"/>
</svg>
```

- viewBox encodes the em: x ∈ [0, advance], y flipped (SVG y-down): top = −880 (ascender),
  height 1000. One `<path>` element; cubic segments only (`M/C/L/Z`).
- The **build step re-reads these SVGs** — hand edits in any vector editor are honored.
  Parser accepts only this restricted subset (single path, no transforms, no CSS, no external
  refs); anything else → `E_GLYPH_SVG_INVALID`. This is a hard security boundary (§17.4).

### 9.5 Warning taxonomy

| Code | Trigger | Effect |
|---|---|---|
| `LOW_INK` | ink ratio < 1.5% but ≥ 0.5% | glyph kept, flagged in review/report |
| `TOUCHES_BORDER` | ink component touches cell inset boundary | flagged (likely cut stroke) |
| `TINY_CONTOURS_REMOVED` | §9.2 cleanup dropped specks | informational |
| `LARGE_INK_BLOB` | ink ratio > 40% | flagged (likely smudge/scan defect) |
| `OFF_GUIDE` | §9.3 clamp applied | flagged |

### 9.6 v2 extension hook (AI completion)

```python
class GlyphCompleter(Protocol):
    def complete(self, have: GlyphSet, want: Sequence[int]) -> Iterable[Glyph]: ...
```

Registered via entry point group `glyphlab.completers`. v1 ships no implementation; the build
command exposes `--completer none` only. No other v1 code path references completion.

---

## 10. Font build

### 10.1 Inputs & outputs

Input: project config (§12.2) + glyph SVGs with status `ACCEPTED` (or `AUTO` when
`include_unreviewed = true`, the CLI default with warning). Output: `build/<family>-v<n>.ttf`,
`.woff2`, `qa-report.json`, `proof.html`.

Missing drawn glyphs are simply absent from the font (no placeholder); the proof sheet and
`status` command list them.

### 10.2 Assembly (fontTools.fontBuilder)

1. Order glyphs: `.notdef`, then by codepoint. Glyph names: AGL where available else `uniXXXX`.
2. Cubic contours → quadratic via `fontTools.cu2qu` (max error 1.0 unit) → `glyf`.
3. Tables: `head` (unitsPerEm 1000, created/modified from `SOURCE_DATE_EPOCH` if set — builds
   must be reproducible), `hhea`/`OS/2` (§10.3), `cmap` (format 4 + format 12), `hmtx`, `name`
  (§10.4), `post` (v2 names), `maxp`, `gasp` (rangeGaspBehavior smooth).
4. WOFF2 export via fontTools `flavor="woff2"` (brotli).

### 10.3 Vertical metrics

| Field | Value |
|---|---|
| OS/2 sTypoAscender / hhea.ascender | 880 |
| OS/2 usWinAscent / usWinDescent | max(880, actual yMax) / max(120, −actual yMin) |
| OS/2 sTypoDescender / hhea.descender | −120 |
| sTypoLineGap / lineGap | 0 |
| OS/2 fsType | 0 (installable — user owns their font) |
| ulCodePageRange1 | bit 17 (JIS/Shift-JIS) + bit 0 (Latin 1) for `ja-basic-v1` |

### 10.4 Naming & metadata

- Family name = project `family_name` (validated: 1–31 chars, `[A-Za-z0-9 \-]`, §12.2 — TTF
  name-table constraint), style "Regular" only in v1.
- `name` ID 0 (copyright): "© <year> <author?>. Generated with glyphlab — the font and the
  handwriting it embodies belong to its author."; ID 5 version `Version <n>.000`;
  ID 11/14 project URL & license note. License of the *font*: user-owned; glyphlab claims
  nothing (README + proof sheet state this).

---

## 11. QA gate & proofing

### 11.1 fontbakery gate

`glyphlab.qa.run_fontbakery(ttf_path)` invokes `fontbakery check-universal --json <out>
--no-progress --loglevel WARN <ttf>` as a subprocess; results parsed into
`QAReport {passed: bool, findings: [QAFinding]}` where
`QAFinding = {check_id, severity: FAIL|WARN|SKIPPED|ALLOWED, message, detail}`
(check filtering happens via the allowlist below, not via fontbakery configuration files).
Gate policy: any `FAIL` not in the checked-in allowlist
(`packages/core/src/glyphlab/qa/allowlist.toml`, each entry with a justification comment) fails
the build with `E_QA_FAILED`. Allowlist calibrated on first golden build (KU-4).

Caller policy (`require_bakery`): CLI `build` requires the fontbakery pass unless the user
passes `--skip-bakery` (fontbakery missing without that flag is an error with an install
hint); service builds and CI always require it. Structural checks (§11.2) can never be
skipped.

### 11.2 Structural self-checks (fast, always on)

- cmap covers exactly: encoded charset ∩ (accepted/included glyphs) + synthesized.
- Every `kana`/`punct_ja` glyph advance == 1000; U+0020 == 500; U+3000 == 1000; every
  advance ≥ 120.
- No empty outlines for drawn glyphs; contours within x ∈ [−200, 2000], y ∈ [−250, 1000].
- head/hhea/OS/2 values exactly as §10.3.

### 11.3 HTML proof sheet

Self-contained `proof.html` (no external requests, CSP meta `default-src 'none'; style-src
'unsafe-inline'; font-src data:; img-src data:`): embeds WOFF2 as data URI, renders (a) full
glyph grid in charset order with status/warning badges, (b) pangram samples — Japanese いろは
+ ASCII "The quick brown fox…" + mixed-script paragraph, (c) missing-glyph list, (d) build
metadata (charset, version, date, glyph counts). All interpolated strings HTML-escaped
(project names are untrusted, §17.4).

---

## 12. Local project directory (CLI)

### 12.1 Layout

```
myfont/
├── glyphlab.toml          # project config (§12.2)
├── template/
│   ├── ja-basic-v1.pdf
│   └── template.json      # sidecar (§7.2)
├── scans/                 # user drops photos/scans here (any names)
├── work/                  # machine-managed: rectified pages, cell PNGs, ingest reports
│   └── ingest-<ts>.json
├── glyphs/                # canonical, user-editable
│   ├── U+3042.svg
│   └── status.json        # {codepoint: {status, warnings, source}}
└── build/
    ├── MyHand-v1.ttf / .woff2
    ├── qa-report.json
    └── proof.html
```

`work/` is disposable cache (documented); `glyphs/` + `glyphlab.toml` + `template/` are the
project state. `status.json` writes are atomic (write-temp + rename).

### 12.2 `glyphlab.toml` (schema v1, pydantic-validated)

```toml
schema = "glyphlab.project/1"
[project]
name = "my handwriting"        # 1–64 chars (NFC), control chars & leading/trailing space forbidden
family_name = "MyHand"         # TTF family constraint (§10.4)
charset = "ja-basic-v1"        # preset id, or path to custom charset TOML
version = 1                    # font version integer

[build]
include_unreviewed = true      # AUTO glyphs included (CLI default)
vectorizer = "auto"            # auto|potrace|potracer

[custom_charset]               # only when charset is a path (CLI-only feature)
# file with: name, version, chars = ["U+0041", "U+3042-U+3044", ...]
```

---

## 13. CLI reference

Entry point `glyphlab` (typer). Global flags: `--project PATH` (default `.`), `--json`
(machine-readable output to stdout), `--verbose`.

| Command | Behavior |
|---|---|
| `glyphlab new NAME --charset ja-basic-v1 [--family-name X]` | Create project dir + `glyphlab.toml`. Refuses non-empty dir. |
| `glyphlab charset list` / `charset show ID` | List presets / print exact codepoints + cell counts. |
| `glyphlab template` | Generate `template/*.pdf` + `template.json` for the project charset. Idempotent (same template_id kept unless `--regenerate`). |
| `glyphlab ingest [scans/...]` | Run §8 on given files (default: all new files in `scans/`), write glyph SVGs + status + `work/ingest-*.json` report; print per-page/per-cell summary table. |
| `glyphlab status` | Coverage table: total/accepted/auto/rejected/missing (+ per-warning counts); `--missing` lists codepoints. |
| `glyphlab accept CODEPOINTS…` / `reject CODEPOINTS…` | Set review status. Accepts `U+3042`, literal `あ`, or ranges `U+3041-U+3096`, or `--all-auto`. |
| `glyphlab build` | §10 + §11; prints artifact paths + QA summary. |

Exit codes: 0 ok · 1 unexpected error · 2 usage error · 3 validation/input error (E_IMG_*,
E_PAGE_*) · 4 QA gate failed. Human-readable errors always go to stderr; in `--json` mode
stdout additionally carries exactly one machine envelope (`{"ok": false, "error": …}` on
failure) so stdout always parses as JSON. The CLI performs no network I/O whatsoever (§17.2
B5).

---

## 14. Service architecture

### 14.1 Components & runtime

Single container: FastAPI (uvicorn, exactly 1 web process) + a job dispatcher thread that
executes each job in a **spawned child process** (`multiprocessing`, spawn context; default
concurrency **1**, env-tunable) + a periodic sweeper (asyncio task, hourly). Child-process
execution is what makes the hard job timeout real: on timeout the parent `terminate()`s the
child — no abandoned threads can keep mutating state. Children never touch the DB: they
receive paths/bytes + config, run pure core-library calls, and return results over the
process pipe; all DB/store writes happen in the parent. Single machine pinned (ADR-005);
SQLite (WAL) on a volume by default, `DATABASE_URL` may select Postgres.

### 14.2 DB schema (SQLAlchemy models; Alembic-managed)

```
projects   (id UUID PK, token_hash BYTES UNIQUE NOT NULL,  -- SHA-256 of secret
            name TEXT NOT NULL, family_name TEXT NOT NULL,
            charset_id TEXT NOT NULL, charset_version INT NOT NULL,
            template_id UUID NOT NULL,
            created_at, last_accessed_at, expires_at)       -- UTC
tombstones (project_id UUID PK, purged_at NOT NULL)         -- §14.4 forensics, 30-day rows
abuse_events (id UUID PK, ip TEXT NOT NULL, kind TEXT CHECK IN
              (rate_limited|auth_miss|quota), created_at)   -- §17.7 abuse log, 7-day rows
uploads    (id UUID PK, project_id FK CASCADE, sha256, bytes INT, mime TEXT,
            page_index INT NULL, status TEXT CHECK IN
              (received|processing|processed|failed),
            error_code TEXT NULL, created_at)
glyphs     (project_id FK, codepoint INT, status TEXT CHECK IN
              (missing|auto|accepted|rejected),
            advance INT NULL, warnings JSON, svg_key TEXT NULL,
            source_upload_id FK NULL, updated_at,
            PRIMARY KEY (project_id, codepoint))
jobs       (id UUID PK, project_id FK CASCADE, type TEXT CHECK IN (ingest|build),
            status TEXT CHECK IN (queued|running|succeeded|failed|canceled),
            payload JSON, error_code TEXT NULL, attempts INT DEFAULT 0,
            lease_expires_at NULL, created_at, started_at, finished_at)
artifacts  (id UUID PK, project_id FK CASCADE, kind TEXT CHECK IN
              (template_pdf|template_sidecar|ttf|woff2|proof_html|qa_json),
            storage_key TEXT, bytes INT, sha256, created_at)
            -- template_sidecar is internal-only: never served by any endpoint
```

Object-store keys: `projects/<project_id>/{uploads|glyphs|artifacts}/<name>` where
`<name>` is server-generated and matches exactly
`^(?:[0-9a-f]{32}(\.[a-z0-9]{1,8})?|U\+[0-9A-F]{4,6}\.svg)$` (uuid4-hex with optional
extension, or the glyph-SVG form). Client input never reaches key construction
(path-traversal impossible by construction).

### 14.3 Job state machine

```
queued → running → succeeded
   ▲        ├───→ failed          (error_code set; attempts+1)
   │        └───→ (lease expiry) → queued   if attempts < 2 else failed(E_JOB_LOST)
canceled ← queued (project deletion only)
```

Claim: single `UPDATE jobs SET status='running', started_at=now(), lease_expires_at=now()+180s
WHERE id=(SELECT id … status='queued' ORDER BY created_at LIMIT 1) RETURNING *` — works on
SQLite (immediate transaction) and Postgres (`FOR UPDATE SKIP LOCKED` variant).

Execution (§14.1): the dispatcher runs each claimed job in a spawned child process and waits
up to **150 s**; on timeout it `terminate()`s (then kills) the child and marks the job
`failed` — the hard timeout is enforced by process death, not cooperation. The child performs
no DB access; the parent applies returned results transactionally, renewing the lease every
30 s while the child runs. Queue caps: ≤ 5 queued jobs per project (`E_RATE_LIMITED`).

### 14.4 Retention & deletion

- `expires_at = last_accessed_at + RETENTION_DAYS` (default **14**); any authenticated project
  request touches `last_accessed_at` (throttled to 1 write/hour).
- Hourly sweeper: for expired projects → delete object-store prefix, delete rows, write
  `purged_at` tombstone row (id + purged_at only) kept 30 days for support/abuse forensics.
- `DELETE /api/projects/{id}` purges immediately (same code path).
- Uploads' original images are deleted from the object store as soon as their ingest job
  reaches a terminal state (only derived cell/glyph data is retained) — data minimization.

---

## 15. HTTP API contract

Base `/api`. Auth: `Authorization: Bearer glp_<secret>` — required on everything except
`POST /projects`, `GET /healthz`, `GET /meta`. The token is generated server-side at project
creation: 32 random bytes (`secrets.token_bytes`), base64url, prefix `glp_`; stored only as
SHA-256; compared via `hmac.compare_digest`. Unknown project id and bad token are
indistinguishable: both `404 {error: E_NOT_FOUND}` (no oracle). Tokens never appear in URLs,
logs, or error messages.

Error envelope (all non-2xx): `{"error": {"code": "E_…", "message": "…", "detail": {...}}}`.
`message` is English, UI translates by `code`.

| Method & path | Req → Resp (2xx) | Notes |
|---|---|---|
| `POST /projects` | `{name, family_name, charset_id}` → `201 {project_id, token, charset, retention_days, template_pages}` | Token returned **once**. Rate-limited hard (§17.6). |
| `GET /projects/{id}` | → `{name, family_name, charset, counts{missing,auto,accepted,rejected}, expires_at}` | |
| `DELETE /projects/{id}` | → `204` | Immediate purge. |
| `GET /projects/{id}/template.pdf` | → `application/pdf` | Generated once, cached as artifact. |
| `POST /projects/{id}/uploads` | multipart `file` → `202 {upload_id, job_id, deduplicated: false}`; same-content re-upload while the matching ingest job is still queued/running → `200 {upload_id, job_id, deduplicated: true}` (existing ids); terminal-job re-upload creates a fresh upload/job | Validations §17.4; enqueues ingest job unless active-job dedup applies. |
| `GET /projects/{id}/jobs/{job_id}` | → `{status, error_code?, result?}` | UI polls ≤ 1 Hz. |
| `GET /projects/{id}/glyphs?status=&warning=` | → `{glyphs: [{codepoint, char, status, advance, warnings, svg_url?, updated_at}], next_cursor?}` | Paged (limit ≤ 300, cursor = last codepoint). |
| `GET /projects/{id}/glyphs/{cp}.svg` | → `image/svg+xml` | Served with `Content-Type` + `nosniff` + restrictive CSP header; SVGs are generator-produced (§9.4). |
| `POST /projects/{id}/glyphs:review` | `{accept: [cp…], reject: [cp…]}` → `200 {updated}` | |
| `POST /projects/{id}/builds` | `{}` → `202 {job_id}` | Rejects if a build job is queued/running. |
| `GET /projects/{id}/artifacts` | → `{artifacts: [{id, kind, bytes, sha256, created_at}]}` | Build outputs only (ttf/woff2/proof_html/qa_json); `template_*` kinds never listed. |
| `GET /projects/{id}/artifacts/{artifact_id}` | → binary | `Content-Disposition: attachment` (except proof_html: inline allowed — self-contained w/ CSP). `template_*` kinds → 404. Hosted builds use fixed font version 1 (`{family}-v1.ttf`); the CLI-side `project.version` concept has no service counterpart. |
| `GET /healthz` / `GET /meta` | liveness / `{version, retention_days, charsets: [{id, version, encoded, drawn, pages}]}` | Unauthenticated, minimal. |

OpenAPI: FastAPI-generated spec is exported to `packages/service/openapi.json`, committed, and
CI fails if the generated spec drifts from the committed one (contract pinning). The webui API
client is generated from this file.

---

## 16. Web UI

SPA (Vite + React + TS), served by the service container at `/` (same origin as API → no CORS
in production; dev uses Vite proxy). State: React Query polling for jobs; no global store.

### 16.1 Routes

| Route | Purpose |
|---|---|
| `/` | Landing: product explanation + "Create project" (name, family name, charset preset) + "Open existing" (paste token) |
| `/p/{project_id}` | Project home: coverage stats, step-by-step checklist (template → upload → review → build) |
| `/p/{project_id}/upload` | Drag-drop upload (≤ 6 files at once), per-file job progress, per-page results incl. error explanations (ja) |
| `/p/{project_id}/review` | Glyph grid (charset order), SVG previews, status filters, tap to accept/reject, bulk "accept all AUTO" |
| `/p/{project_id}/build` | Build trigger, job progress, artifact list, live preview (`@font-face` from woff2 artifact URL + editable sample textarea), download buttons |

### 16.2 Token handling (security-relevant)

- On create: token displayed once in a "save this" panel (copy button + warning that loss =
  unrecoverable) and stored in `localStorage` keyed by project id.
- Shareable link format: `/p/{id}#t={token}` — the token rides the **fragment** (never sent to
  the server, never in server logs); on load the SPA moves it fragment → localStorage and
  strips the fragment via `history.replaceState`.
- All API calls send the token via `Authorization` header. The token is never put in query
  strings.

### 16.3 Error & warning strings (ja — canonical table)

Every `E_*` code from §22 maps to exactly these user-facing strings (the `ja.ts` table is
generated/checked against this list; unknown codes fall back to
「エラーが発生しました（{code}）」):

| Code | ja message (+ remediation) |
|---|---|
| `E_IMG_FORMAT` | 対応していない画像形式です。JPEG・PNG・HEICでアップロードしてください |
| `E_IMG_TOO_LARGE` | 画像が大きすぎます。12MB・3600万画素以内にしてください |
| `E_IMG_DECODE` | 画像を読み込めませんでした。別の写真で試してください |
| `E_PAGE_NO_MARKERS` | 四隅のマーカーが見つかりません。ページ全体が写るように撮り直してください |
| `E_PAGE_AMBIGUOUS` | 複数のページが写っています。1枚ずつ撮影してください |
| `E_PAGE_UNKNOWN` | このプロジェクトのテンプレートではないページです |
| `E_PAGE_WARPED` | 用紙の歪みが大きすぎます。平らな場所で真上から撮り直してください |
| `E_PAGE_BLURRY` | 写真がぶれています。明るい場所で、ページ全体が入るように撮り直してください |
| `E_TEMPLATE_MISMATCH` | テンプレートが現在の設定と一致しません |
| `E_TRACE_UNAVAILABLE` | サーバー内部エラー（変換エンジン未設定）。時間をおいて再試行してください |
| `E_TRACE_TIMEOUT` | 処理が時間内に終わりませんでした。画像を確認して再試行してください |
| `E_GLYPH_SVG_INVALID` | グリフデータが不正です |
| `E_QA_FAILED` | フォントの品質チェックに失敗しました。レポートを確認してください |
| `E_NOT_FOUND` | プロジェクトが見つからないか、リンクが無効・期限切れです |
| `E_RATE_LIMITED` | アクセスが集中しています。しばらく待って再試行してください |
| `E_QUOTA_EXCEEDED` | 容量または回数の上限に達しました |
| `E_REQUEST_TOO_LARGE` | リクエストが大きすぎます |
| `E_JOB_LOST` | 処理が中断されました。もう一度お試しください |
| `E_BUILD_IN_PROGRESS` | フォント生成がすでに実行中です。完了をお待ちください |
| `E_VALIDATION` | 入力内容に誤りがあります |
| `E_INTERNAL` | サーバーエラーが発生しました。時間をおいて再試行してください |

Warning chip labels (§9.5 codes): `LOW_INK` 「インクが薄い」, `TOUCHES_BORDER`
「枠に接触」, `TINY_CONTOURS_REMOVED` 「微小なゴミを除去」, `LARGE_INK_BLOB`
「インクが多すぎる可能性」, `OFF_GUIDE` 「ガイド外（自動調整済み）」.

### 16.4 Accessibility & scope guardrails

Keyboard navigable review grid; no analytics/trackers; no external CDN assets (all bundled) —
consistent with the proof-sheet CSP posture.

### 16.5 Language

UI strings live in `webui/src/i18n/ja.ts` (single flat string table, typed keys). v1 ships
`ja` only; the table indirection is the v2 i18n seam (D8).

---

## 17. Security model

### 17.1 Assets & actors

Assets: (a) users' handwriting images & derived glyphs/fonts (personal data — handwriting is
biometric-adjacent), (b) project tokens, (c) service availability, (d) integrity of released
packages/images. Actors: anonymous internet users (benign + abusive), the operator (trusted),
CI infrastructure (semi-trusted).

### 17.2 Trust boundaries

```
[Internet] ──TLS──▶ [PaaS proxy] ─▶ [FastAPI: auth, limits, validation]   ← B1: every request
                                        │
                                        ▼
                        [job worker: image parsing, potrace subprocess]   ← B2: untrusted bytes
                                        │
                                        ▼
                              [DB / ObjectStore]                          ← B3: server-generated keys only
[User's browser] ◀── fonts/SVGs/HTML produced by our generator ──         ← B4: output encoding
[CLI user's machine]: local files only; no network calls at all           ← B5
```

### 17.3 Threat table (v1 mitigations are requirements, not suggestions)

| # | Threat | Boundary | Mitigation (issue-enforced) |
|---|---|---|---|
| T1 | Malicious image (decompression bomb, format exploit) | B2 | Header pre-checks (dimensions/pixels) before decode; `MAX_IMAGE_PIXELS`; size cap 12 MiB; only JPEG/PNG/HEIC via Pillow/pillow-heif; decode in worker with 150 s job timeout; no ImageMagick/exiftool subprocesses |
| T2 | Token brute force / enumeration | B1 | 256-bit tokens; hashed at rest; uniform 404; per-IP rate limits; no project listing endpoint |
| T3 | Token leakage via URL/logs | B1/B4 | Token only in header + URL fragment (§16.2); logging policy forbids Authorization/token fields (structured logger redacts); tokens excluded from error messages |
| T4 | Abuse: storage exhaustion | B1 | Per-project caps: ≤ 40 uploads, ≤ 100 MiB storage, ≤ 5 queued jobs; global disk watermark check → 507; per-IP project-creation limit (10/day) |
| T5 | Abuse: CPU exhaustion (trace bombs — adversarial noise images maximize potrace work) | B2 | potrace subprocess 10 s timeout + job child-process concurrency 1 with 150 s kill-enforced timeout; binarization/despeckle bounds component count (≤ 64) before trace |
| T6 | Path traversal / key injection | B3 | Keys built only from server UUIDs + enum kinds (§14.2); ObjectStore API takes structured key parts, never client strings; LocalDiskStore resolves & asserts prefix containment as defense-in-depth |
| T7 | XSS via project/family name or SVG | B4 | Names validated at ingest (length, charset §12.2); proof-sheet/HTML outputs escape everything; glyph SVGs are generator-emitted only, restricted-subset-validated on read (§9.4), served with `nosniff` + CSP; React default-escapes UI strings |
| T8 | Malicious font attacking downloaders' renderers | B4 | Fonts are built by our assembler from validated outlines (never re-served from user upload); fontbakery + structural checks; artifacts downloadable only with the project token (no public gallery) |
| T9 | SSRF | B1 | Service makes **zero** outbound requests by design; no URL-fetch features in v1 |
| T10 | Dependency compromise | supply chain | `uv.lock` committed; CI `pip-audit` + `npm audit` + Dependabot; GitHub Actions pinned to commit SHAs; release builds from CI only |
| T11 | Secrets leakage | ops | Only secrets: `DATABASE_URL?`, S3 creds (optional). Set by human via `fly secrets` (never committed); `.env` gitignored; settings loader refuses to log config; repo secret-scan before publicizing (already public: enforced by CI gitleaks) |
| T12 | Cross-project data access | B1/B3 | Every query filtered by `project_id` resolved **from the token**, never from client-supplied id alone (id must match token's project or 404) |

### 17.4 Input validation table (B1/B2 entry points)

| Input | Rules |
|---|---|
| `name` / `family_name` | §12.2 constraints; NFC-normalized; control chars rejected; no leading/trailing whitespace |
| `charset_id` | must be a known preset id (enum) |
| Upload file | MIME sniff (magic bytes) must match JPEG/PNG/HEIC; declared Content-Length and actual size ≤ 12 MiB; multipart parsed with size-capped streaming to temp file |
| `codepoint` params | int within project charset |
| `page_index` | derived from markers server-side; client hint ignored |
| Glyph SVG (build-time re-read) | restricted subset parser (§9.4); reject > 256 KiB, > 64 contours, or > 4000 segments |
| Custom charset TOML (CLI-only) | file ≤ 4096 bytes; expanded set ≤ 500 drawn chars (§7.1 marker budget); every entry a valid Unicode scalar value; never accepted by the service |

### 17.5 Platform hardening

- HTTP responses: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
  `Permissions-Policy: camera=(), microphone=(), geolocation=()`,
  `Cross-Origin-Opener-Policy: same-origin`, `Cross-Origin-Resource-Policy: same-origin`;
  CSP for HTML/SPA responses: `default-src 'self'; img-src 'self' data:; font-src 'self'
  data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'`; CSP for API JSON:
  `default-src 'none'`. HSTS at proxy. Route-specific CSPs (§15 SVG/proof) override the
  middleware defaults.
- Container: non-root user, read-only rootfs except `/data` volume + `/tmp`, no shell needed at
  runtime (potrace + python only), minimal base (python:3.12-slim-bookworm), `HEALTHCHECK`.
- CORS: production same-origin → no CORS headers; dev-only allowlist via env flag.

### 17.6 Rate limits (slowapi; defaults, env-tunable)

| Scope | Limit |
|---|---|
| `POST /projects` | 10/day + 3/min per IP |
| `POST uploads` | 20/hour per project, 40/hour per IP |
| `POST builds` | 10/hour per project |
| any authenticated | 120/min per IP |
| 429 body | error envelope `E_RATE_LIMITED` + `Retry-After` |

### 17.7 Privacy posture

Handwriting is personal data: no accounts, no email, no analytics, IP addresses only in
short-retention (7 days) abuse logs, originals deleted post-ingest (§14.4), whole-project TTL
14 days, one-click purge. A plain-language privacy page (ja) ships with the web UI; SECURITY.md
defines a vulnerability-report channel (GitHub private security advisories).

---

## 18. Testing & validation strategy

### 18.1 Layers

| Layer | Tooling | Gate |
|---|---|---|
| Unit (core) | pytest, mypy --strict, ruff | every PR |
| Golden pipeline | synthetic scan corpus (§18.2) → byte-stable glyph SVG + font-table assertions | every PR |
| Property | hypothesis on charset/fitting math (advance ≥ 120, contours closed, mapping monotonic) | every PR |
| Service API | pytest + httpx TestClient + temp SQLite + LocalDiskStore; schemathesis against committed openapi.json | every PR |
| Storage | moto for S3Store; containment tests for LocalDiskStore | every PR |
| Security regression | abuse suite: oversized/malformed uploads, wrong tokens, cross-project attempts, rate-limit trips, traversal attempts | every PR |
| Web E2E | Playwright vs docker-compose stack, happy path + error path | main + release |
| Font QA | fontbakery universal on golden font | every PR |

### 18.2 Synthetic scan corpus (the keystone)

A fixture generator renders *filled* templates programmatically: take template PDF pages →
raster → stamp glyph images (drawn from a bundled open-license handwriting-style font) into
cells → apply parameterized distortions (perspective warp ≤ 15°, rotation ≤ 5°, Gaussian noise,
illumination gradient, JPEG q=70, shadow band). Deterministic via fixed seed. This yields
end-to-end tests with known expected cmap coverage and per-glyph ink, with zero real
handwriting needed. Corpus profiles: `clean-scan`, `phone-tilt`, `phone-dark`, `crumpled`
(worst-case, allowed to fail with correct error codes).

### 18.3 v1 acceptance (product-level)

The v1 completion test (final issue) runs: CLI journey on `clean-scan` + `phone-tilt` corpora →
font installs (macOS `fontutil`-less check: fontbakery pass + cmap assertions) → service
journey via Playwright on docker-compose → retention sweeper unit-clock test → security abuse
suite green.

---

## 19. Observability

- Structured JSON logs (stdlib logging + formatter): request id, project id, job id, error
  codes; **never** tokens, filenames, or image bytes. Uvicorn access log off; custom concise
  access log.
- `/healthz` liveness (DB ping + store write probe); `/meta` exposes version + charset ids.
- Counters via periodic log line (jobs by status, projects active, storage bytes) — no metrics
  stack in v1 (documented ops limitation).

## 20. Packaging & deployment

- **PyPI**: `glyphlab` (core+CLI). `uv build`; Trusted Publishing from GitHub Actions on tag;
  TestPyPI dry-run job. Version scheme: `0.x.y` until v1 → `1.0.0`.
- **Docker**: multi-stage — stage 1 builds webui (`npm ci && npm run build`), stage 2
  python:3.12-slim + `apt-get install potrace` + uv-installed packages + webui static; final
  image runs `glyphlab-service` (uvicorn) as non-root. Compose file: service + volume
  (self-host default SQLite/local store).
- **Fly.io**: `deploy/fly.toml` (1 machine, `min_machines_running=1`, volume mount `/data`,
  internal port, health checks) + `deploy/RUNBOOK.md` with exact human steps (`fly launch
  --no-deploy`, `fly volumes create`, `fly secrets set …`, `fly deploy`) — secrets are
  human-set per repo policy.
- Env config (pydantic-settings, prefix `GLYPHLAB_`): `ENVIRONMENT` (`dev`|`prod`),
  `DATA_DIR`, `DATABASE_URL`, `OBJECT_STORE` (`local`|`s3`), S3 vars (`S3_ENDPOINT_URL`,
  `S3_BUCKET`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`),
  `RETENTION_DAYS`, `SWEEP_INTERVAL_S`, `WEBUI_DIST`, limit overrides (issue 26's field
  list is canonical), `PUBLIC_BASE_URL`.

## 21. Performance budgets

| Operation | Budget |
|---|---|
| Ingest one page (49 cells, potrace binary) | ≤ 15 s on 1 vCPU |
| Ingest one page (potracer fallback) | ≤ 120 s (CLI-only path, warned) |
| Font build (278 glyphs) | ≤ 10 s |
| Template PDF generation (6 pages) | ≤ 5 s |
| Service memory ceiling | ≤ 800 MiB total RSS (web parent ≤ 300 MiB + 1 job child ≤ 500 MiB peak); Fly VM sized 1 GB (§20) |

## 22. Error code registry (canonical)

| Code | HTTP | CLI exit | Meaning |
|---|---|---|---|
| `E_IMG_FORMAT` | 415 | 3 | Unsupported/unrecognized image format |
| `E_IMG_TOO_LARGE` | 413 | 3 | Byte size or pixel count over cap |
| `E_REQUEST_TOO_LARGE` | 413 | 3 | Non-upload request body over cap |
| `E_IMG_DECODE` | 422 | 3 | Image failed to decode |
| `E_PAGE_NO_MARKERS` | 422 | 3 | Fewer than 4 fiducials of one page found |
| `E_PAGE_AMBIGUOUS` | 422 | 3 | Markers of ≥ 2 pages in one photo |
| `E_PAGE_UNKNOWN` | 422 | 3 | Page not in this project's template |
| `E_PAGE_WARPED` | 422 | 3 | Rectification quality gate failed |
| `E_PAGE_BLURRY` | 422 | 3 | Sharpness gate failed |
| `E_TEMPLATE_MISMATCH` | 409 | 3 | Scan's template ≠ project charset/template |
| `E_TRACE_UNAVAILABLE` | 500 | 3 | No vectorizer engine available |
| `E_TRACE_TIMEOUT` | 500 | 3 | Tracing exceeded its time limit |
| `E_GLYPH_SVG_INVALID` | 422 | 3 | Glyph SVG failed the restricted parser |
| `E_QA_FAILED` | 422 | 4 | Font QA gate failed |
| `E_NOT_FOUND` | 404 | 3 | Unknown resource / bad token (uniform) |
| `E_RATE_LIMITED` | 429 | 3 | Rate/queue limit hit |
| `E_QUOTA_EXCEEDED` | 409 (507 global) | 3 | Project/global quota exceeded |
| `E_JOB_LOST` | 500 | 1 | Job lease expired past retry budget |
| `E_BUILD_IN_PROGRESS` | 409 | 3 | A build job is already queued/running |
| `E_VALIDATION` | 422 | 3 | Input validation failed (machine `detail`) |
| `E_INTERNAL` | 500 | 1 | Unexpected error |

Every code additionally has a ja UI string (§16.3). The registry (issue 06) carries exactly
these HTTP/CLI mappings; adding a code = updating this table + the registry + the ja map
(enforced by a registry unit test).

### Implementation clarification: Windows clipping bounds

The fitting contract permits ink within y ∈ [−250, 1000], including Latin
descenders below −120. Fixed Windows bounds would clip valid handwriting and
fail Font Bakery's `family/win_ascent_and_descent` check. Windows bounds therefore
expand to the actual compiled glyph extrema, with a minimum of 880/120. Typo
and hhea metrics remain 880/−120/0. This resolves the earlier fixed-win-metrics
conflict without changing fitting or disabling clipping checks.

Format 4 and format 12 cmap tables remain mandatory even for ASCII-only fonts.
Font Bakery's `cmap/format_12` recommendation against a redundant table is
allowlisted; independent structural QA requires format 4 to cover selected BMP codepoints and
format 12 to cover all selected Unicode scalars (including supplementary planes).
