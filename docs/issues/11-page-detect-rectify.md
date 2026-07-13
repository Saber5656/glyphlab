# Title

Ingest S2–S4: ArUco detection, page identification, rectification

# Summary

From a sanitized grayscale image, detect the four page fiducials, identify which template page
it is, and warp it onto the canonical 2481×3508 raster, enforcing the DESIGN §8.2 quality
gates (`E_PAGE_NO_MARKERS`, `E_PAGE_AMBIGUOUS`, `E_PAGE_UNKNOWN`, `E_PAGE_WARPED`,
`E_PAGE_BLURRY`).

# Context

This stage is the robustness heart of the paper workflow (ADR-003): phone photos arrive
tilted, dim, and noisy; the marker-based approach must absorb that or fail with an actionable
error.

# Scope

`packages/core/src/glyphlab/ingest/rectify.py` + tests against the issue-09 corpus.

# Detailed Requirements

1. `detect_and_rectify(img: np.ndarray, sidecar: TemplateSidecar) -> RectifiedPage`
   where `RectifiedPage = {page_index: int, canvas: np.ndarray (2481×3508 uint8),
   diagnostics: {reproj_error_px, sharpness, marker_ids, attempts}}`.
2. Detection ladder per §8.2 S2 (stop at first success, record attempt count):
   a. `ArucoDetector(DICT_4X4_50, DetectorParameters())` on the input.
   b. CLAHE contrast enhancement (`clipLimit=3, tileGridSize=8×8`) then detect.
   c. 1.5× upscale (if longest side < 3000 px) then detect; if this attempt succeeds, record
      `detection_scale=1.5` and divide all returned marker corner coordinates by 1.5 before
      they are used as source points against the original image.
   After the ladder: group detected IDs by page (`id // 4`). Ambiguity rule per §8.2 S3:
   ≥ 2 page groups with ≥ 2 markers each → `E_PAGE_AMBIGUOUS` (two sheets in frame); a
   single stray marker from another page is recorded in diagnostics and ignored. The
   winning group needs all 4 distinct corner roles; none has them → `E_PAGE_NO_MARKERS`.
3. Page identification: `page_index = id // 4` must exist in the sidecar → else
   `E_PAGE_UNKNOWN`. Corner role from `id % 4` (0 TL, 1 TR, 2 BR, 3 BL) per issue 07.
4. Homography (deterministic): correspondences = all 16 detected marker corners; for each
   marker, ArUco returns its 4 corners in order (marker-TL, marker-TR, marker-BR,
   marker-BL) — map each to the same-ordered corner of that marker's rect from the sidecar,
   converted to canonical px. Estimate with `cv2.findHomography(src16, dst16, method=0)`
   (least squares over ID-validated points — no RANSAC, no RNG, fully deterministic). Source
   points are always in the coordinate system of the original `img`; fallback-upscale detections
   are scaled back first. Warp
   with `cv2.warpPerspective(img, H, dsize=(2481, 3508))` (dsize is (width, height); the
   resulting ndarray shape is `(3508, 2481)` = (rows, cols)), white border fill.
5. Quality gates (§8.2 S4):
   - Reprojection: apply H to the 16 source corners; RMS distance to their sidecar
     destinations > 3.0 px → `E_PAGE_WARPED`.
   - Sharpness: variance of Laplacian over the warped grid region < 60.0 (tunable constant,
     calibrated in KU-3; single named constant) → `E_PAGE_BLURRY`.
6. Sidecar-geometry-driven: all canonical positions come from the sidecar object (issue 07
   note about honoring old printed sheets), not from layout constants.
7. Failure diagnostics: every `E_PAGE_*` raise carries `detail` (issue 06's
   `GlyphlabError.detail`) = `{"attempts": int, "marker_ids": [...], "reproj_error_px":
   float | null, "sharpness": float | null}` — the same fields as success diagnostics.
8. Tests: corpus `clean-scan` and `phone-tilt` pages 0–5 rectify with reproj ≤ 3 px and
   correct page_index; `phone-dark` rectifies OR fails with `E_PAGE_BLURRY` — pin the
   actual outcome as golden, and if it fails, open the ISSUE_PLAN KU-3 follow-up issue
   (adaptive marker detection retry ladder) as part of landing this one; `crumpled` fails
   with a code in {`E_PAGE_WARPED`, `E_PAGE_BLURRY`, `E_PAGE_NO_MARKERS`}; a photo of
   page 1 against a page-0-only sidecar → `E_PAGE_UNKNOWN`; two pages composited side by
   side → `E_PAGE_AMBIGUOUS`; blank white image → `E_PAGE_NO_MARKERS`; determinism: same
   input bytes twice → byte-identical canvas. Also a smoke test that the installed OpenCV
   major version exposes `cv2.aruco.ArucoDetector` (KU-2 canary).

# Acceptance Criteria

- [ ] All corpus assertions above green on Ubuntu and macOS CI.
- [ ] Diagnostics populated (attempts, reproj, sharpness) for success AND failure paths.
- [ ] No OpenCV GUI functions referenced (headless-safe).

# Validation

```bash
uv run pytest packages/core/tests/ingest/test_rectify.py -q
```

# Dependencies

07, 09, 10.

# Non-goals

Cell-level processing (12), retry/UX messaging (16.3 strings — issue 39), detector parameter
auto-tuning (KU-3 follow-up).

# Design References

DESIGN §8.2 S2–S4, §7.1/§7.2 (markers, sidecar), §2.4 KU-2/KU-3, ADR-003.
