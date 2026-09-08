from glyphlab.charset import CharDef
from glyphlab.fit.cleanup import clean_outline
from glyphlab.fit.fitting import fit_glyph
from glyphlab.ingest.cells import CellGeometry
from glyphlab.model import Contour, GlyphWarning, Point
from glyphlab.template.layout import GuideGeometry
from glyphlab.vectorize.geometry import line_segment


def rectangle(x0, y0, x1, y1):
    points = [Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1)]
    return Contour(tuple(line_segment(points[i], points[(i + 1) % 4]) for i in range(4)))


def test_latin_fitting_and_clamp():
    geom = CellGeometry(65, "latin", (0, 0, 0), (0, 0, 250, 250), GuideGeometry(175, 95))
    char = CharDef(65, "latin", True)
    glyph = fit_glyph([rectangle(30, 95, 100, 175)], geom, char, [])
    assert glyph.advance == 522
    assert min(s.p1.x for c in glyph.outline.contours for s in c.segments) == 60
    assert max(s.p1.y for c in glyph.outline.contours for s in c.segments) == 460
    big = fit_glyph([rectangle(0, -200, 500, 400)], geom, char, [])
    assert GlyphWarning.OFF_GUIDE in big.warnings
    assert all(-250 <= s.p1.y <= 1000 for c in big.outline.contours for s in c.segments)


def test_union_and_drop_tiny():
    outline, warnings = clean_outline(
        [
            rectangle(0, 0, 100, 100),
            rectangle(50, 0, 150, 100),
            rectangle(200, 0, 201, 1),
        ],
        min_contour_area=40,
    )
    assert len(outline.contours) == 1
    assert GlyphWarning.TINY_CONTOURS_REMOVED in warnings
