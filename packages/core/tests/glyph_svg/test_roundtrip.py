from pathlib import Path
from tempfile import TemporaryDirectory

from glyphlab.model import Contour, CubicSegment, GlyphOutline, Point
from glyphlab.project.glyph_svg import read_glyph_svg, write_glyph_svg
from hypothesis import given
from hypothesis import strategies as st


@st.composite
def outlines(draw: st.DrawFn) -> GlyphOutline:
    values = draw(
        st.lists(
            st.floats(min_value=-200, max_value=200, allow_nan=False, allow_infinity=False),
            min_size=6,
            max_size=12,
        ).map(lambda items: [round(item, 2) for item in items])
    )
    points = [Point(values[index], values[index + 1]) for index in range(0, len(values) - 1, 2)]
    first = points[0]
    segments = tuple(
        CubicSegment(start, start, end, end)
        for start, end in zip(points, [*points[1:], first], strict=True)
    )
    return GlyphOutline((Contour(segments),))


@given(outline=outlines())
def test_write_read_roundtrip(outline: GlyphOutline) -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "glyph.svg"
        write_glyph_svg(path, outline, 0x41, 600)
        parsed, advance = read_glyph_svg(path)
        assert advance == 600
        assert parsed == outline
