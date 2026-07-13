# Research: Font Generation & Image Processing Ecosystem (Python)

- Date: 2026-07-08
- Status: informs DESIGN.md §9–§11 and ADR-001/ADR-004
- Method: PyPI JSON API version checks + vendor docs review

## Question

Which libraries can implement the pipeline *scan image → binarized cells → vector outlines →
installable font* with (a) mature, well-documented APIs that a lower-capability implementation
agent can use mechanically, and (b) licenses compatible with MIT distribution?

## Findings

### Font assembly

| Library | Version (2026-07-08) | Role | Notes |
|---|---|---|---|
| `fonttools` | 4.63.0 | TTF/WOFF2 assembly | De-facto standard. `fontTools.fontBuilder` builds a full TTF (glyf, cmap, hmtx, name, OS/2, post, head, hhea, maxp). `fontTools.cu2qu` (bundled) converts cubic→quadratic for `glyf`. WOFF2 flavor requires `brotli`. |
| `brotli` | 1.2.0 | WOFF2 compression | Required by fontTools for WOFF2 save. |
| `ufoLib2` | 0.18.1 | UFO intermediate | **Not needed for v1** — fontBuilder direct build is simpler; UFO adds a format layer without a v1 consumer. Revisit if v2 needs editing interop. |
| `fontbakery` | 1.1.0 | Font QA | CLI: `fontbakery check-universal font.ttf --html report.html`. The *universal* profile checks OpenType compliance without Google-Fonts-specific opinions. Suitable as an automated QA gate with an explicit allowlist of accepted findings. |
| `skia-pathops` | 0.9.2 | Path boolean ops | `pathops.union` removes stroke overlaps and fixes contour orientation — required because traced handwriting frequently self-overlaps. Used by fontTools ecosystem itself. |

### Bitmap tracing (vectorization)

| Option | Version | Assessment |
|---|---|---|
| `potrace` (C binary) | 1.16 (distro package) | Battle-tested tracer, GPL-2 **binary invoked via subprocess** (no license contamination of MIT code; we do not link). Fast (<50 ms/glyph). Available via `apt-get install potrace` (Docker) and `brew install potrace`. |
| `potracer` (pure Python) | 0.0.4 | Pure-Python port of potrace 1.16, intentionally API-compatible, GPL-2. ~500× slower than C but acceptable for ≤300 glyphs offline. Zero install friction (`pip`). **GPL-2 as an *optional* extra dependency must be documented; core stays MIT by importing it lazily and only if installed.** |
| `pypotrace` (C bindings) | 0.3 (stale) | Known build/install problems across OSes. Rejected. |

Decision candidate (→ ADR-004): a `VectorizerEngine` interface with two implementations —
`PotraceBinaryEngine` (subprocess, preferred; guaranteed present in the service Docker image) and
`PotracerEngine` (pure-Python fallback for pip-only local installs, optional extra
`glyphlab[trace]`). GPL note: subprocess invocation and optional runtime import keep the MIT
license of glyphlab itself intact; the constraint is documented in README licensing section.

### Image processing

| Library | Version | Role |
|---|---|---|
| `opencv-python-headless` | 5.0.0.93 | ArUco fiducial detection (`cv2.aruco.ArucoDetector`, API stable since 4.7), homography rectification, adaptive thresholding, morphology. Headless variant avoids GUI deps in Docker. **OpenCV 5.x is current; the ArUco API used must be smoke-tested against 5.x in CI (known unknown KU-2).** |
| `pillow` | 12.3.0 | Image decode, EXIF orientation, resizing. `Image.MAX_IMAGE_PIXELS` must be set explicitly as a decompression-bomb guard. |
| `pillow-heif` | 1.4.0 | HEIC/HEIF decode (iPhone photos). Registers a Pillow plugin. |

### PDF template generation

| Option | Version | Assessment |
|---|---|---|
| `fpdf2` | 2.8.7 | Pure-Python, LGPL-3 → **license concern for bundling? LGPL is import-safe (not derivative), acceptable** but heavier to reason about. Simple cell/image API. |
| `reportlab` | 5.0.0 | BSD-3. Industry standard, precise mm-based canvas API, embeds PNG (ArUco markers) trivially. |

Decision: **reportlab** (BSD license aligns with MIT distribution; precise coordinate control
needed for a print-accurate template).

### CLI / service stack

| Library | Version | Role |
|---|---|---|
| `typer` | 0.26.8 | CLI framework (click-based, typed) |
| `pydantic` / `pydantic-settings` | 2.13.4 / 2.14.2 | Config & schema validation |
| `fastapi` | 0.139.0 | HTTP API |
| `uvicorn` | 0.50.2 | ASGI server |
| `python-multipart` | 0.0.32 | multipart upload parsing for FastAPI |
| `sqlalchemy` / `alembic` | 2.0.51 / 1.18.5 | ORM + migrations (SQLite & Postgres) |
| `slowapi` | 0.1.10 | Rate limiting for FastAPI (per-IP/per-key) |
| `boto3` | 1.43.42 | S3-compatible object storage client |
| `httpx` | 0.28.1 | API client for tests |
| `schemathesis` | 4.22.3 | OpenAPI contract testing |
| `moto` | 5.2.2 | S3 mocking in tests |
| `pip-audit` / `bandit` | 2.10.1 / 1.9.4 | Dependency & static security scanning in CI |
| `playwright` | 1.61.0 | Web UI E2E |

### Package name availability

`glyphlab` returns 404 on `https://pypi.org/pypi/glyphlab/json` as of 2026-07-08 → **name is
free on PyPI**. Register early in the packaging issue (squatting risk noted in ISSUE_PLAN known
unknowns).

## Sources

- https://pypi.org/ JSON API (versions above, retrieved 2026-07-08)
- https://pypi.org/project/potracer/ — pure-Python potrace port, pypotrace API compatibility
- https://potrace.sourceforge.net/ — potrace C tool
- https://docs.opencv.org/4.x/d2/d1a/classcv_1_1aruco_1_1ArucoDetector.html — ArucoDetector API
- https://fontbakery.readthedocs.io/en/latest/user/USAGE.html — `check-universal` CLI usage
