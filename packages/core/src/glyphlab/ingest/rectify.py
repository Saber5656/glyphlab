"""Deterministic ArUco-based page recognition and rectification."""

from dataclasses import dataclass
from typing import Any, NoReturn

import cv2
import numpy as np

from glyphlab.errors import GlyphlabError
from glyphlab.template.layout import MM_TO_PX, RASTER_SIZE
from glyphlab.template.pdf import MARKER_QUIET_MM
from glyphlab.template.sidecar import TemplateSidecar

SHARPNESS_THRESHOLD = 60.0


@dataclass(frozen=True)
class RectifiedPage:
    page_index: int
    canvas: np.ndarray
    diagnostics: dict[str, Any]


def detect_and_rectify(img: np.ndarray, sidecar: TemplateSidecar) -> RectifiedPage:
    detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50))
    diagnostics: dict[str, Any] = {
        "attempts": 0,
        "marker_ids": [],
        "reproj_error_px": None,
        "sharpness": None,
        "detection_scale": 1.0,
    }

    def fail(code: str, message: str) -> NoReturn:
        raise GlyphlabError(code, message, detail=diagnostics.copy())

    found = {}
    attempts = [(img, 1.0), (None, 1.0)]
    if max(img.shape) < 3000:
        attempts.append((None, 1.5))
    for index, (candidate, scale) in enumerate(attempts):
        if index == 1:
            candidate = cv2.createCLAHE(clipLimit=3, tileGridSize=(8, 8)).apply(img)
        if scale == 1.5:
            candidate = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        if candidate is None:
            continue
        corners, ids, _ = detector.detectMarkers(candidate)
        diagnostics["attempts"] = index + 1
        diagnostics["detection_scale"] = scale
        found = (
            {}
            if ids is None
            else {
                int(i): c.reshape(4, 2) / scale for i, c in zip(ids.flatten(), corners, strict=True)
            }
        )
        diagnostics["marker_ids"] = sorted(found)
        groups = {i // 4 for i in found}
        counts = {g: sum(i // 4 == g for i in found) for g in groups}
        if sum(n >= 2 for n in counts.values()) >= 2:
            fail("E_PAGE_AMBIGUOUS", "Multiple pages detected")
        if any(n == 4 for n in counts.values()):
            break
    winning = [g for g in {i // 4 for i in found} if all(4 * g + r in found for r in range(4))]
    if not winning:
        fail("E_PAGE_NO_MARKERS", "Four page markers could not be found")
    index = winning[0]
    page = next((p for p in sidecar.pages if p.index == index), None)
    if page is None:
        fail("E_PAGE_UNKNOWN", "Page is not present in the template")
    diagnostics["stray_marker_ids"] = [i for i in sorted(found) if i // 4 != index]
    src: list[Any] = []
    dst = []
    for marker_id, rect in zip(page.aruco_ids, page.marker_rects_mm(), strict=True):
        x0, y0, x1, y1 = rect
        # The PDF's quiet zone is inside each sidecar marker rect. Detection returns
        # ink corners; fitting these to the outer rectangle would distort the grid.
        quiet = page.content_mm.marker * MARKER_QUIET_MM / 14
        x0 += quiet
        y0 += quiet
        x1 -= quiet
        y1 -= quiet
        dst.extend(
            [
                (x0 * MM_TO_PX, y0 * MM_TO_PX),
                (x1 * MM_TO_PX, y0 * MM_TO_PX),
                (x1 * MM_TO_PX, y1 * MM_TO_PX),
                (x0 * MM_TO_PX, y1 * MM_TO_PX),
            ]
        )
        src.extend(found[marker_id])
    source = np.array(src, dtype=np.float64)
    target = np.array(dst, dtype=np.float64)
    h, _ = cv2.findHomography(source, target, method=0)
    if h is None or not np.isfinite(h).all():
        fail("E_PAGE_WARPED", "Page transform is degenerate")
    projected = cv2.perspectiveTransform(source.reshape(-1, 1, 2), h).reshape(-1, 2)
    error = float(np.sqrt(np.mean(np.sum((projected - target) ** 2, axis=1))))
    diagnostics["reproj_error_px"] = error
    if error > 3:
        fail("E_PAGE_WARPED", "Page reprojection exceeds tolerance")
    canvas = cv2.warpPerspective(img, h, RASTER_SIZE, borderValue=255)
    g = page.grid_mm
    x0 = int(g.x0 * MM_TO_PX)
    y0 = int(g.y0 * MM_TO_PX)
    x1 = int((g.x0 + g.cols * g.cell + (g.cols - 1) * g.gap) * MM_TO_PX)
    y1 = int((g.y0 + g.rows * (g.cell + g.label_h) + (g.rows - 1) * g.gap) * MM_TO_PX)
    sharpness = float(cv2.Laplacian(canvas[y0:y1, x0:x1], cv2.CV_64F).var())
    diagnostics["sharpness"] = sharpness
    if sharpness < SHARPNESS_THRESHOLD:
        fail("E_PAGE_BLURRY", "Page is too blurry")
    return RectifiedPage(index, canvas, diagnostics)
