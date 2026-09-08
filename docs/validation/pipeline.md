# Scan pipeline validation and interpretation notes

The pipeline's integration tests use actual generated PDFs, PDFium rasterization,
Klee One handwriting glyphs, seeded scan distortions, ArUco detection, native
potrace, pathops cleanup, fitting, and the restricted SVG writer. Tests do not
replace these stages with successful stubs. Narrow failure-injection tests cover
trace timeouts and detector retry ordering separately.

## Reproduction

Install the workspace development dependencies and native potrace. Then run:

```sh
uv run pytest packages/core/tests/template packages/core/tests/corpus \
  packages/core/tests/ingest packages/core/tests/vectorize packages/core/tests/fit -q
uv run python packages/core/tests/template/update_golden.py
uv run python packages/core/tests/corpus/generate.py \
  --profile phone-tilt --page 0 --seed 42 --out /tmp/glyphlab-corpus
```

The golden updater regenerates the printable page at 150 dpi and two 128-square
clean-scan crops. Fixture generation is seeded; production pipeline code uses no
randomness. The font and corpus remain outside `src/` and the wheel.

## Geometry and darkness decisions

The template marker rectangle includes a 1.75 mm white quiet zone on every side.
ArUco detects the black 10.5 mm marker's corners, not the 14 mm rectangle's outer
corners. Consequently all sixteen detected ink corners are matched to the
sidecar rectangle inset by the renderer's quiet-zone ratio. Matching the detected
ink to the outside rectangle, as a literal reading of issue 11 suggested, would
introduce systematic geometric error. Content corners remain the documented
(12,36), (198,36), (198,283), and (12,283) mm positions.

Cell crops use the persisted writing box with a 2 mm inset. Guide anchors remain
relative to the complete writing box, translated into the crop's coordinate
system; the inset does not redefine the printed baseline or x-height. Custom
charset script classes are supplied to slicing by the orchestrator.

Otsu splits any two-tone image, including an entirely blank printed template.
After illumination normalization, the binarizer therefore also requires an ink
value at most 170/255. This removes 20%-gray guides while retaining the intended
darker pen marks. A fully unfilled page is explicitly tested as 49 empty cells.
High-frequency checkerboards are rejected before morphology can erase evidence
of hostile complexity; surviving connected components are separately capped at
64 before tracing.

## Observed coverage and limitations

- `clean-scan` and `phone-tilt`: all six pages identify and rectify within the
  3-pixel reprojection gate; page 0 matches its exact 48-inked/1-empty manifest.
- `phone-dark`: page 0 rectifies and matches its manifest exactly. The current
  calibrated 60.0 Laplacian threshold did not require a KU-3 fallback issue.
- `crumpled`: rejected by the documented page quality codes.
- Native and Python engines agree at least 97% filled-raster IoU on ten seeded
  procedural blob inputs. The `potracer` distribution imports as `potrace`; its
  bitmap API uses the opposite boolean polarity from glyphlab's ink bitmaps.
- Fitting preserves holes, unions overlapping curves, uses uniform clamps, and
  keeps integer output coordinates. Latin guide mapping can legitimately extend
  to the documented [-250,1000] ink envelope beyond nominal font metrics.
- These are synthetic image results. No physical printed/scanned sheet or real
  phone photograph has been validated by this implementation task.
