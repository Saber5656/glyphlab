import cv2
import numpy as np
from glyphlab.charset import CharDef
from glyphlab.fit.cleanup import clean_outline, signed_area
from glyphlab.fit.fitting import fit_glyph
from glyphlab.ingest.cells import CellGeometry
from glyphlab.model import Contour, Point
from glyphlab.template.layout import GuideGeometry
from glyphlab.vectorize import TraceOpts, select_engine
from glyphlab.vectorize.geometry import line_segment
from hypothesis import given, settings
from hypothesis import strategies as st


def rectangle(x, y, w, h):
    points = [Point(x, y), Point(x + w, y), Point(x + w, y + h), Point(x, y + h)]
    return Contour(tuple(line_segment(points[i], points[(i + 1) % 4]) for i in range(4)))


@settings(max_examples=100, derandomize=True)
@given(
    x=st.integers(-100, 100),
    y=st.integers(-100, 300),
    w=st.integers(3, 250),
    h=st.integers(3, 250),
    latin=st.booleans(),
)
def test_metrics_closure_and_uniform_clamping(x, y, w, h, latin):
    char = CharDef(65 if latin else 0x3042, "latin" if latin else "kana", True)
    geom = CellGeometry(
        char.codepoint,
        char.script_class,
        (0, 0, 0),
        (0, 0, 250, 250),
        GuideGeometry(175, 95) if latin else GuideGeometry(square=(15, 15, 235, 235)),
    )
    glyph = fit_glyph([rectangle(x, y, w, h)], geom, char, [])
    assert glyph.advance >= 120
    if not latin:
        assert glyph.advance == 1000
    assert all(c.segments[0].p1 == c.segments[-1].p2 for c in glyph.outline.contours)
    points = [s.p1 for c in glyph.outline.contours for s in c.segments]
    assert min(p.y for p in points) >= -250 and max(p.y for p in points) <= 1000
    if latin:
        assert min(p.x for p in points) == 60
    else:
        assert abs((min(p.x for p in points) + max(p.x for p in points)) / 2 - 500) <= 0.5
    assert all(float(p.x).is_integer() and float(p.y).is_integer() for p in points)


def test_cleanup_preserves_counter_orientation():
    yy, xx = np.mgrid[:100, :100]
    bitmap = ((xx - 50) ** 2 + (yy - 50) ** 2 < 40**2) & ((xx - 50) ** 2 + (yy - 50) ** 2 > 20**2)
    contours = select_engine("potrace").trace(bitmap, TraceOpts())
    outline, warnings = clean_outline(contours, min_contour_area=40)
    assert len(outline.contours) == 2 and warnings == []
    assert signed_area(outline.contours[0]) * signed_area(outline.contours[1]) < 0


def test_cleanup_unions_overlapping_curves():
    a = np.zeros((100, 100), np.uint8)
    b = a.copy()
    cv2.circle(a, (35, 50), 25, 1, -1)
    cv2.circle(b, (65, 50), 25, 1, -1)
    engine = select_engine("potrace")
    contours = engine.trace(a.astype(bool), TraceOpts()) + engine.trace(b.astype(bool), TraceOpts())
    outline, _ = clean_outline(contours, min_contour_area=40)
    assert len(outline.contours) == 1
