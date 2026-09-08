import pytest
from glyphlab.model import (
    Contour,
    CubicSegment,
    GlyphOutline,
    GlyphStatus,
    GlyphWarning,
    Point,
)


def _square() -> GlyphOutline:
    p = Point
    return GlyphOutline(
        (
            Contour(
                (
                    CubicSegment(p(0, 0), p(0, 0), p(10, 0), p(10, 0)),
                    CubicSegment(p(10, 0), p(10, 0), p(10, 10), p(10, 10)),
                    CubicSegment(p(10, 10), p(10, 10), p(0, 0), p(0, 0)),
                )
            ),
        )
    )


def test_geometry_and_status() -> None:
    outline = _square()
    assert outline.bbox() == (0, 0, 10, 10)
    assert outline.transform(2, 5, -1).bbox() == (5, -1, 25, 19)
    assert GlyphStatus.AUTO.value == "auto"
    assert GlyphWarning.LOW_INK.value == "LOW_INK"


def test_contour_must_be_closed() -> None:
    p = Point
    with pytest.raises(ValueError):
        Contour((CubicSegment(p(0, 0), p(0, 0), p(1, 0), p(1, 0)),))
