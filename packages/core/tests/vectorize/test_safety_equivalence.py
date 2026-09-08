import subprocess
from types import ModuleType

import cv2
import numpy as np
import pytest
from glyphlab.errors import GlyphlabError
from glyphlab.vectorize import TraceOpts, select_engine


def raster(contours):
    canvas = np.zeros((180, 180), np.uint8)
    polygons = []
    for contour in contours:
        points = []
        for segment in contour.segments:
            for t in np.linspace(0, 1, 32):
                u = 1 - t
                points.append(
                    (
                        u**3 * segment.p1.x
                        + 3 * u * u * t * segment.c1.x
                        + 3 * u * t * t * segment.c2.x
                        + t**3 * segment.p2.x,
                        u**3 * segment.p1.y
                        + 3 * u * u * t * segment.c1.y
                        + 3 * u * t * t * segment.c2.y
                        + t**3 * segment.p2.y,
                    )
                )
        polygons.append(np.round(points).astype(np.int32))
    cv2.fillPoly(canvas, polygons, 1)
    return canvas.astype(bool)


@pytest.mark.parametrize(
    "binary,fallback", [(True, True), (True, False), (False, True), (False, False)]
)
def test_selection_availability_matrix(monkeypatch, binary, fallback):
    monkeypatch.setattr("glyphlab.vectorize.potrace_bin.validate_executable", lambda _: None)

    def import_engine():
        if not fallback:
            raise ImportError
        return ModuleType("potrace")

    if not binary and not fallback:
        with pytest.raises(GlyphlabError, match="glyphlab\\[trace\\]"):
            select_engine("auto", _which=lambda _: None, _import_potracer=import_engine)
    else:
        engine = select_engine(
            "auto",
            _which=lambda _: "/available/potrace" if binary else None,
            _import_potracer=import_engine,
        )
        assert engine.name == ("potrace" if binary else "potracer")


def test_binary_timeout_and_invalid_bitmap(monkeypatch):
    engine = select_engine("potrace")

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("potrace", 10)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(GlyphlabError) as error:
        engine.trace(np.ones((20, 20), bool), TraceOpts())
    assert error.value.code == "E_TRACE_TIMEOUT"
    with pytest.raises(GlyphlabError) as error:
        engine.trace(np.ones((1300, 1300), bool), TraceOpts())
    assert error.value.code == "E_VALIDATION"


def test_binary_failure_is_bounded(monkeypatch):
    engine = select_engine("potrace")
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 1, b"", b"x" * 1000)
    )
    with pytest.raises(GlyphlabError) as error:
        engine.trace(np.ones((20, 20), bool), TraceOpts())
    assert error.value.code == "E_INTERNAL"
    assert len(error.value.detail["stderr"]) == 200


@pytest.mark.parametrize("seed", range(10))
def test_native_fallback_filled_raster_equivalence(seed):
    rng = np.random.default_rng(seed)
    bitmap = np.zeros((180, 180), np.uint8)
    points = rng.integers(20, 160, size=(12, 2)).astype(np.int32)
    cv2.fillConvexPoly(bitmap, cv2.convexHull(points), 1)
    bitmap = cv2.GaussianBlur(bitmap.astype(np.float32), (0, 0), 3) > 0.5
    native = raster(select_engine("potrace").trace(bitmap, TraceOpts()))
    fallback = raster(select_engine("potracer").trace(bitmap, TraceOpts()))
    assert np.count_nonzero(native & fallback) / np.count_nonzero(native | fallback) >= 0.97


def test_native_page_trace_performance_budget():
    from time import perf_counter

    engine = select_engine("potrace")
    yy, xx = np.mgrid[:250, :250]
    bitmap = (xx - 125) ** 2 + (yy - 125) ** 2 < 80**2
    start = perf_counter()
    for _ in range(49):
        engine.trace(bitmap, TraceOpts())
    assert perf_counter() - start <= 5
