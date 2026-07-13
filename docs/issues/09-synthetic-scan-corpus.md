# Title

Synthetic scan corpus generator (deterministic test fixtures)

# Summary

Build the fixture engine of DESIGN §18.2: programmatically "handwrite" a template (stamp glyph
raster images into cells), then apply parameterized photo-realistic distortions, producing
deterministic corpora (`clean-scan`, `phone-tilt`, `phone-dark`, `crumpled`) with ground-truth
manifests. Every ingest/E2E test depends on this.

# Context

The pipeline cannot be tested mechanically against real handwriting. A synthetic corpus with
known ground truth (which codepoints are inked, where) converts the whole pipeline into
golden-testable code — the keystone of the validation strategy.

# Scope

`packages/core/tests/corpus/` generator package (test-support code; hatchling packages only
`src/`, so nothing under `tests/` can reach the wheel — wheel-content assertions live in
issue 47). Strategy: **on-demand generation with a `pytest` session-scoped cache** to keep
the repo slim; commit only 2 tiny golden crops.

# Detailed Requirements

1. Rendering: rasterize the given template PDF pages (pypdfium2, dev dependency added in
   08) at 300 dpi → clean page raster.
2. "Handwriting": for each drawn cell, render the target character using the bundled
   open-license font `packages/core/tests/corpus/fonts/KleeOne-Regular.ttf` (SIL OFL 1.1,
   covers kana + Latin; vendored together with `packages/core/tests/corpus/fonts/OFL.txt`)
   at randomized-but-seeded size/offset/rotation (±5%, ±1 mm, ±3°), rasterized dark gray
   (intensity 30–60), composited into the cell's writing box. A seeded fraction (default
   3%) of cells left empty to exercise `EMPTY` classification; manifest records which.
3. Distortion profiles (all seeded, parameters in one dataclass per profile; the concrete
   numbers below are the canonical implementation of DESIGN §18.2's envelope — DESIGN's
   "warp ≤ 15°, rotation ≤ 5°" bounds must hold):
   - `clean-scan`: none + slight gaussian blur σ=0.5.
   - `phone-tilt`: perspective warp with corners displaced ≤ 6% of the page dimension
     (≈ 12–15° camera tilt, within the ≤ 15° envelope), rotation ≤ 4°, JPEG re-encode
     q=70, mild vignette.
   - `phone-dark`: `phone-tilt` + brightness ×0.55 + gaussian noise σ=6 + illumination
     gradient (linear, 25% swing).
   - `crumpled`: strong local sinusoidal displacement + shadow bands — expected to FAIL
     rectification with `E_PAGE_WARPED`/`E_PAGE_BLURRY` (negative fixture).
4. Manifest: one JSON file per page, `page-<k>.manifest.json`, exactly:
   `{"schema": "glyphlab.corpus-manifest/1", "profile": str, "seed": int,
   "template_id": str, "page_index": int, "inked": ["U+0021", ...],
   "empty_cells": ["U+0041", ...]}` — codepoints as sorted `U+XXXX` strings; `inked` and
   `empty_cells` partition the page's mapped cells. Images written alongside as
   `page-<k>.<png|jpg>`.
5. API: `generate_corpus(template_pdf: Path, sidecar: TemplateSidecar, profile: str,
   pages: list[int] | None, seed: int, out_dir: Path, fill_fraction: float = 1.0) ->
   list[Path]` (manifest paths). `fill_fraction` scales how many mapped cells receive
   handwriting (`0.0` → fully unfilled pages, used by issue 12's guide-suppression test;
   the seeded 3% empty cells apply on top of the filled subset).
   Taking the template artifacts as inputs keeps `template_id` aligned with the consuming
   project (issue 25 requirement). Pytest fixture `corpus_page(profile, page)` generates a
   default-template corpus with session-scoped caching keyed by (profile, seed, sidecar
   geometry hash).
6. Determinism: identical seed ⇒ byte-identical PNG/JPEG outputs (use numpy RNG
   `default_rng(seed)`, no wall clock; JPEG encode via Pillow with fixed params).
7. Output-validity guard: every generated image must itself pass the §8.2 S1 limits
   (≤ 12 MiB, ≤ 36 MP, sniffable JPEG/PNG magic) — asserted in tests so fixtures can
   always flow through the real upload path.
8. Performance: full `ja-basic-v1` 6-page corpus for one profile ≤ 60 s on CI.

# Acceptance Criteria

- [ ] Two consecutive generations with the same seed are byte-identical.
- [ ] `clean-scan` page 0 golden crop matches committed golden within tolerance.
- [ ] Manifests validate against the schema above and list exactly the seeded-empty cells.
- [ ] `KleeOne-Regular.ttf` + `OFL.txt` vendored at the exact paths above.
- [ ] Generated images pass the S1 validity guard.

# Validation

```bash
uv run pytest packages/core/tests/corpus -q
uv run python packages/core/tests/corpus/generate.py --profile phone-tilt --page 0 --seed 42 --out /tmp/corpus
ls /tmp/corpus  # expect page-0.jpg + page-0.manifest.json
```

# Dependencies

07, 08.

# Non-goals

Ingest itself (10–15), real-photo test collection (post-v1 human validation), performance
optimization beyond the CI budget.

# Design References

DESIGN §18.2 (profiles, determinism), §8.2 (stages the corpus must exercise), §7.1 (geometry).
